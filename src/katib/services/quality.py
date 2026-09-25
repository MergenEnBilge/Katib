"""Dataset health report and the class gallery listing."""

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from katib.core.quality import (
    BoxItem,
    duplicate_shapes,
    imbalance_ratio,
    is_tiny,
    near_duplicates,
)
from katib.core.types import geometry_bounds
from katib.db.models import Annotation, Class, Image
from katib.services.projects import get_project

SAMPLE = 100
MAX_PAGE = 200


@dataclass
class ImageRef:
    id: uuid.UUID
    filename: str


@dataclass
class HealthReport:
    images: int
    annotations: int
    empty_images: int = 0
    empty_sample: list[ImageRef] = field(default_factory=list[ImageRef])
    tiny_shapes: int = 0
    tiny_sample: list[uuid.UUID] = field(default_factory=list[uuid.UUID])
    duplicate_shapes: int = 0
    duplicate_sample: list[uuid.UUID] = field(default_factory=list[uuid.UUID])
    class_counts: list[tuple[str, int]] = field(default_factory=list[tuple[str, int]])
    imbalance: float | None = None
    look_alikes: list[list[ImageRef]] = field(default_factory=list[list[ImageRef]])


def bounds_of(type_name: str, geometry: dict[str, Any]) -> tuple[float, float, float, float] | None:
    """The rectangle around a shape, or None for shapes that do not sit anywhere, like tags."""
    if type_name == "tag":
        return None
    return geometry_bounds(type_name, geometry)


def project_health(session: Session, project_id: uuid.UUID) -> HealthReport:
    get_project(session, project_id)
    images = session.scalar(select(func.count(Image.id)).where(Image.project_id == project_id)) or 0
    per_class = session.execute(
        select(Class.name, func.count(Annotation.id))
        .outerjoin(Annotation, Annotation.class_id == Class.id)
        .where(Class.project_id == project_id)
        .group_by(Class.id)
        .order_by(Class.position)
    ).all()
    total = sum(n for _, n in per_class)
    report = HealthReport(images=images, annotations=total)
    report.class_counts = [(name, n) for name, n in per_class]
    report.imbalance = imbalance_ratio([n for _, n in per_class])

    has_shapes = select(Annotation.id).where(Annotation.image_id == Image.id).exists()
    empties = select(Image.id, Image.filename).where(Image.project_id == project_id, ~has_shapes)
    report.empty_images = session.scalar(select(func.count()).select_from(empties.subquery())) or 0
    report.empty_sample = [
        ImageRef(i, f) for i, f in session.execute(empties.order_by(Image.position).limit(SAMPLE))
    ]

    items: list[BoxItem] = []
    rows = session.execute(
        select(
            Annotation.id,
            Annotation.image_id,
            Annotation.class_id,
            Annotation.type,
            Annotation.geometry,
        )
        .join(Image, Image.id == Annotation.image_id)
        .where(Image.project_id == project_id)
        .order_by(Annotation.image_id)
    ).yield_per(5000)
    for ann_id, image_id, class_id, type_name, geometry in rows:
        found_bounds = bounds_of(type_name, geometry)
        if found_bounds is None:
            continue
        x, y, w, h = found_bounds
        if is_tiny(w, h):
            report.tiny_shapes += 1
            if len(report.tiny_sample) < SAMPLE:
                report.tiny_sample.append(ann_id)
        items.append(BoxItem(str(ann_id), str(image_id), str(class_id), x, y, w, h))
    dupes = duplicate_shapes(items)
    report.duplicate_shapes = len(dupes)
    report.duplicate_sample = [uuid.UUID(b) for _, b in dupes[:SAMPLE]]

    hashes: dict[str, int] = {}
    names: dict[str, ImageRef] = {}
    for image_id, filename, phash in session.execute(
        select(Image.id, Image.filename, Image.phash).where(
            Image.project_id == project_id, Image.phash.is_not(None)
        )
    ):
        if phash:
            hashes[str(image_id)] = int(phash, 16)
            names[str(image_id)] = ImageRef(image_id, filename)
    report.look_alikes = [[names[k] for k in group] for group in near_duplicates(hashes)[:SAMPLE]]
    return report


@dataclass
class GalleryRow:
    annotation: Annotation
    filename: str
    image_status: str


@dataclass
class GalleryPage:
    rows: list[GalleryRow]
    next: uuid.UUID | None


def list_shapes(
    session: Session,
    project_id: uuid.UUID,
    *,
    class_id: uuid.UUID | None = None,
    image_status: str | None = None,
    after: uuid.UUID | None = None,
    limit: int = 60,
    tiny_only: bool = False,
) -> GalleryPage:
    """Shapes across the project for the class gallery, oldest first, keyset paginated."""
    get_project(session, project_id)
    limit = max(1, min(limit, MAX_PAGE))
    stmt = (
        select(Annotation, Image.filename, Image.status)
        .join(Image, Image.id == Annotation.image_id)
        .where(Image.project_id == project_id)
        .order_by(Annotation.id)
    )
    if class_id is not None:
        stmt = stmt.where(Annotation.class_id == class_id)
    if image_status:
        stmt = stmt.where(Image.status == image_status)
    if after is not None:
        stmt = stmt.where(Annotation.id > after)
    if not tiny_only:
        rows = [GalleryRow(a, f, s) for a, f, s in session.execute(stmt.limit(limit + 1)).all()]
        nxt = rows[limit - 1].annotation.id if len(rows) > limit else None
        return GalleryPage(rows[:limit], nxt)
    # Tiny shapes need geometry, which is checked in Python, so scan in batches.
    found: list[GalleryRow] = []
    last: uuid.UUID | None = None
    while len(found) <= limit:
        page = stmt.limit(500) if last is None else stmt.where(Annotation.id > last).limit(500)
        batch = session.execute(page).all()
        if not batch:
            break
        for a, f, st in batch:
            last = a.id
            found_bounds = bounds_of(a.type, a.geometry)
            if found_bounds is not None and is_tiny(found_bounds[2], found_bounds[3]):
                found.append(GalleryRow(a, f, st))
        if len(batch) < 500:
            break
    nxt = found[limit - 1].annotation.id if len(found) > limit else None
    return GalleryPage(found[:limit], nxt)
