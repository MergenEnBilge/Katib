"""Pre-labeling: let a detection model draft boxes, which people then correct.

Model boxes are saved like any other shape, marked with source "model" and a confidence so the
canvas draws them dashed. Every run is written to the operations log, so it can be undone as a
whole for as long as undo is kept.
"""

import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from katib.core.detect import Detection
from katib.core.types import Box
from katib.db.ids import new_id
from katib.db.models import Annotation, Image, Operation, Project
from katib.services import class_ops, classes
from katib.services.errors import InvalidInput, NotFound
from katib.services.images import StorageContext, image_path
from katib.storage.local import LocalStorage

log = logging.getLogger(__name__)

Progress = Callable[[float], None]


class Detector(Protocol):
    """What pre-labeling needs from a model. `katib.ml.onnx.OnnxDetector` is one."""

    class_names: list[str] | None

    def detect(self, image_path: Path, threshold: float, iou: float = ...) -> list[Detection]: ...


@dataclass
class PrelabelResult:
    images: int = 0
    shapes: int = 0
    skipped_classes: list[str] = field(default_factory=list[str])
    failed: list[str] = field(default_factory=list[str])
    operation: Operation | None = None


def _plural(n: int, one: str) -> str:
    return f"{n:,} {one}" if n == 1 else f"{n:,} {one}s"


def run(
    session: Session,
    ctx: StorageContext,
    operations: LocalStorage,
    project_id: uuid.UUID,
    detector: Detector,
    *,
    threshold: float,
    only_unlabeled: bool,
    create_missing_classes: bool,
    class_names: Sequence[str] | None = None,
    user_id: uuid.UUID | None = None,
    progress: Progress | None = None,
) -> PrelabelResult:
    """Run `detector` over a project's images and save what it finds as boxes."""
    project = session.get(Project, project_id)
    if project is None:
        raise NotFound("That project does not exist.")
    if "box" not in project.settings.get("annotation_types", ["box", "polygon"]):
        raise InvalidInput("This project does not use boxes, which is what the model draws.")
    names = list(class_names or detector.class_names or [])
    if not names:
        raise InvalidInput(
            "This model does not list its class names. "
            "Type them in, one per class, in the model's order."
        )
    if not 0.0 < threshold <= 1.0:
        raise InvalidInput("The confidence has to be between 0 and 1.")

    result = PrelabelResult()
    class_ids: dict[int, uuid.UUID] = {}
    for index, name in enumerate(names):
        found = classes.resolve_class(session, project_id, name)
        if found is None and create_missing_classes:
            found = classes.create_class(session, project_id, name)
        if found is None:
            result.skipped_classes.append(name)
        else:
            class_ids[index] = found.id
    session.commit()

    stmt = select(Image).where(Image.project_id == project_id).order_by(Image.position)
    if only_unlabeled:
        labeled = select(Annotation.image_id).where(Annotation.image_id == Image.id).exists()
        stmt = stmt.where(~labeled)
    targets = list(session.scalars(stmt))

    created: list[str] = []
    for done, image in enumerate(targets, start=1):
        try:
            detections = detector.detect(image_path(image, ctx), threshold)
        except (OSError, NotFound, ValueError) as err:
            log.warning("Pre-label skipped %s: %s", image.filename, err)
            result.failed.append(image.filename)
            detections = []
        added = 0
        for found in detections:
            class_id = class_ids.get(found.class_index)
            if class_id is None:
                continue
            box = Box(x=found.x, y=found.y, w=found.w, h=found.h)
            annotation = Annotation(
                id=new_id(),
                image_id=image.id,
                class_id=class_id,
                type="box",
                geometry=box.model_dump(),
                source="model",
                confidence=round(found.score, 4),
                created_by=user_id,
            )
            session.add(annotation)
            created.append(str(annotation.id))
            added += 1
        result.shapes += added
        result.images += 1 if added else 0
        # Save as we go. Progress is written from another connection, and SQLite lets only one
        # connection write at a time, so an open transaction here would block it.
        session.commit()
        if progress:
            progress(done / len(targets))
    session.flush()

    if created:
        summary = (
            f"Pre-labeled {_plural(result.images, 'image')} with "
            f"{_plural(result.shapes, 'box')} from a model."
        )
        result.operation = class_ops.record(
            session,
            operations,
            project_id,
            user_id,
            "prelabel",
            summary,
            {"annotation_ids": created},
        )
    session.commit()
    return result
