"""Annotation routes."""

import uuid

from fastapi import APIRouter

from katib.api.deps import SessionDep, UserDep, need
from katib.api.hub import emit
from katib.api.schemas import AnnotationOut, BatchIn, BatchOut, OpResultOut
from katib.services import access, annotations
from katib.services.annotations import Op

router = APIRouter(tags=["annotations"])


@router.get("/images/{image_id}/annotations", response_model=list[AnnotationOut])
def list_annotations(
    image_id: uuid.UUID, session: SessionDep, user: UserDep
) -> list[AnnotationOut]:
    need(session, user, access.project_of_image(session, image_id), "view")
    found = annotations.list_annotations(session, image_id)
    return [AnnotationOut.model_validate(a) for a in found]


@router.post("/images/{image_id}/annotations:batch", response_model=BatchOut)
def batch(image_id: uuid.UUID, body: BatchIn, session: SessionDep, user: UserDep) -> BatchOut:
    need(session, user, access.project_of_image(session, image_id), "annotate")
    ops = [Op(**o.model_dump()) for o in body.ops]
    results = annotations.apply_batch(session, image_id, ops, user.id)
    if any(r.status == "ok" for r in results):
        emit(
            session.info,
            access.project_of_image(session, image_id),
            {"type": "annotation.changed", "image_id": str(image_id), "user_id": str(user.id)},
        )
    return BatchOut(
        results=[
            OpResultOut(
                id=r.id,
                status=r.status,
                annotation=AnnotationOut.model_validate(r.annotation) if r.annotation else None,
                error=r.error,
            )
            for r in results
        ]
    )
