"""Dataset health, the class gallery and shape crops."""

import uuid
from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel

from katib.api.deps import SessionDep, StorageDep, UserDep, need
from katib.db.models import Annotation
from katib.services import access, images, quality
from katib.services.errors import NotFound
from katib.storage.imaging import crop_jpeg

router = APIRouter(tags=["quality"])

CACHE = {"Cache-Control": "private, max-age=3600"}


class ImageRefOut(BaseModel):
    id: uuid.UUID
    filename: str


class ClassCountOut(BaseModel):
    name: str
    count: int


class HealthOut(BaseModel):
    images: int
    annotations: int
    empty_images: int
    empty_sample: list[ImageRefOut]
    tiny_shapes: int
    tiny_sample: list[uuid.UUID]
    duplicate_shapes: int
    duplicate_sample: list[uuid.UUID]
    class_counts: list[ClassCountOut]
    imbalance: float | None
    look_alikes: list[list[ImageRefOut]]


class ShapeOut(BaseModel):
    id: uuid.UUID
    image_id: uuid.UUID
    filename: str
    image_status: str
    class_id: uuid.UUID | None
    type: str
    geometry: dict[str, Any]
    confidence: float | None
    version: int


class ShapePageOut(BaseModel):
    items: list[ShapeOut]
    next: uuid.UUID | None


def _refs(items: list[quality.ImageRef]) -> list[ImageRefOut]:
    return [ImageRefOut(id=i.id, filename=i.filename) for i in items]


@router.get("/projects/{project_id}/health", response_model=HealthOut)
def project_health(project_id: uuid.UUID, session: SessionDep, user: UserDep) -> HealthOut:
    need(session, user, project_id, "view")
    r = quality.project_health(session, project_id)
    return HealthOut(
        images=r.images,
        annotations=r.annotations,
        empty_images=r.empty_images,
        empty_sample=_refs(r.empty_sample),
        tiny_shapes=r.tiny_shapes,
        tiny_sample=r.tiny_sample,
        duplicate_shapes=r.duplicate_shapes,
        duplicate_sample=r.duplicate_sample,
        class_counts=[ClassCountOut(name=n, count=c) for n, c in r.class_counts],
        imbalance=r.imbalance,
        look_alikes=[_refs(g) for g in r.look_alikes],
    )


@router.get("/projects/{project_id}/shapes", response_model=ShapePageOut)
def list_shapes(
    project_id: uuid.UUID,
    session: SessionDep,
    user: UserDep,
    class_id: uuid.UUID | None = None,
    image_status: str | None = None,
    tiny_only: bool = False,
    after: uuid.UUID | None = None,
    limit: int = 60,
) -> ShapePageOut:
    need(session, user, project_id, "view")
    page = quality.list_shapes(
        session,
        project_id,
        class_id=class_id,
        image_status=image_status,
        tiny_only=tiny_only,
        after=after,
        limit=limit,
    )
    return ShapePageOut(
        items=[
            ShapeOut(
                id=r.annotation.id,
                image_id=r.annotation.image_id,
                filename=r.filename,
                image_status=r.image_status,
                class_id=r.annotation.class_id,
                type=r.annotation.type,
                geometry=r.annotation.geometry,
                confidence=r.annotation.confidence,
                version=r.annotation.version,
            )
            for r in page.rows
        ],
        next=page.next,
    )


@router.get("/annotations/{annotation_id}/crop")
def crop(
    annotation_id: uuid.UUID,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    size: int = 160,
) -> Response:
    need(session, user, access.project_of_annotation(session, annotation_id), "view")
    ann = session.get(Annotation, annotation_id)
    if ann is None:
        raise NotFound("That shape does not exist.")
    image = images.get_image(session, ann.image_id)
    x, y, w, h = quality.bounds_of(ann.geometry)
    data = crop_jpeg(images.image_path(image, storage), x, y, w, h, max(32, min(size, 512)))
    headers = {**CACHE, "ETag": f'"{ann.id}-{ann.version}-{size}"'}
    return Response(data, media_type="image/jpeg", headers=headers)
