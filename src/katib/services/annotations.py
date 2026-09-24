"""Annotations: list an image's shapes and apply batches of create, update and delete.

Ids come from the client and operations are idempotent, so a retried batch is safe. Updates and
deletes carry the version the client saw. A mismatch is reported per operation with the current
record and does not stop the rest of the batch (ARCHITECTURE.md section 9).
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from katib.core.attributes import AttributeError_, check_attrs
from katib.core.types import GeometryError, validate_geometry
from katib.db.base import utcnow
from katib.db.models import Annotation, Class, Image, Project
from katib.services.errors import InvalidInput, NotFound
from katib.services.images import get_image

Status = Literal["ok", "conflict", "not_found", "invalid"]
MAX_OPS = 500


@dataclass
class Op:
    op: Literal["create", "update", "delete"]
    id: uuid.UUID
    type: str | None = None
    class_id: uuid.UUID | None = None
    geometry: dict[str, Any] | None = None
    attrs: dict[str, Any] | None = None
    if_version: int | None = None
    patch: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class OpResult:
    id: uuid.UUID
    status: Status
    annotation: Annotation | None = None
    error: str | None = None


def list_annotations(session: Session, image_id: uuid.UUID) -> list[Annotation]:
    get_image(session, image_id)
    stmt = select(Annotation).where(Annotation.image_id == image_id).order_by(Annotation.created_at)
    return list(session.scalars(stmt))


def _check_class(session: Session, image: Image, class_id: uuid.UUID | None) -> None:
    if class_id is None:
        raise InvalidInput("Choose a class for this shape.")
    cls = session.get(Class, class_id)
    if cls is None or cls.project_id != image.project_id:
        raise InvalidInput("That class does not belong to this project.")


def _check_values(session: Session, class_id: uuid.UUID | None, attrs: dict[str, Any]) -> None:
    cls = session.get(Class, class_id) if class_id else None
    if cls is None or not attrs:
        return
    try:
        check_attrs(cls.attr_schema, attrs)
    except AttributeError_ as err:
        raise InvalidInput(str(err)) from err


def _check_type(session: Session, image: Image, type_name: str) -> None:
    project = session.get(Project, image.project_id)
    enabled = (project.settings if project else {}).get("annotation_types", ["box", "polygon"])
    if type_name not in enabled:
        raise InvalidInput(f"This project does not use {type_name} annotations.")


def _create(session: Session, image: Image, op: Op, user_id: uuid.UUID | None) -> OpResult:
    existing = session.get(Annotation, op.id)
    if existing is not None:
        if existing.image_id != image.id:
            return OpResult(op.id, "invalid", error="That id is already used on another image.")
        return OpResult(op.id, "ok", existing)
    try:
        if not op.type or op.geometry is None:
            raise InvalidInput("A new shape needs a type and geometry.")
        _check_type(session, image, op.type)
        _check_class(session, image, op.class_id)
        geometry = validate_geometry(op.type, op.geometry).model_dump()
        _check_values(session, op.class_id, op.attrs or {})
    except (InvalidInput, GeometryError) as err:
        return OpResult(op.id, "invalid", error=str(err))
    ann = Annotation(
        id=op.id,
        image_id=image.id,
        class_id=op.class_id,
        type=op.type,
        geometry=geometry,
        attrs=op.attrs or {},
        created_by=user_id,
    )
    session.add(ann)
    return OpResult(op.id, "ok", ann)


def _update(session: Session, image: Image, op: Op) -> OpResult:
    ann = session.get(Annotation, op.id)
    if ann is None or ann.image_id != image.id:
        return OpResult(op.id, "not_found", error="That shape no longer exists.")
    if op.if_version is not None and op.if_version != ann.version:
        return OpResult(op.id, "conflict", ann, "This shape changed since you loaded it.")
    new_class: uuid.UUID | None = None
    new_geometry: dict[str, Any] | None = None
    new_attrs: dict[str, Any] | None = None
    try:
        unknown = set(op.patch) - {"class_id", "geometry", "attrs"}
        if unknown:
            raise InvalidInput(f"Cannot change {', '.join(sorted(unknown))}.")
        if "class_id" in op.patch:
            raw = op.patch["class_id"]
            new_class = uuid.UUID(str(raw)) if raw else None
            _check_class(session, image, new_class)
        if "geometry" in op.patch:
            new_geometry = validate_geometry(ann.type, op.patch["geometry"]).model_dump()
        if "attrs" in op.patch:
            new_attrs = dict(op.patch["attrs"])
            _check_values(session, new_class or ann.class_id, new_attrs)
    except (InvalidInput, GeometryError, ValueError) as err:
        return OpResult(op.id, "invalid", ann, str(err))
    # Nothing is changed until every part of the patch has passed validation.
    if new_class is not None:
        ann.class_id = new_class
    if new_geometry is not None:
        ann.geometry = new_geometry
    if new_attrs is not None:
        ann.attrs = new_attrs
    ann.version += 1
    ann.updated_at = utcnow()
    return OpResult(op.id, "ok", ann)


def _delete(session: Session, image: Image, op: Op) -> OpResult:
    ann = session.get(Annotation, op.id)
    if ann is None or ann.image_id != image.id:
        return OpResult(op.id, "ok")
    if op.if_version is not None and op.if_version != ann.version:
        return OpResult(op.id, "conflict", ann, "This shape changed since you loaded it.")
    session.delete(ann)
    return OpResult(op.id, "ok")


def apply_batch(
    session: Session, image_id: uuid.UUID, ops: list[Op], user_id: uuid.UUID | None = None
) -> list[OpResult]:
    """Apply operations in order in one transaction. Returns one result per operation."""
    if len(ops) > MAX_OPS:
        raise InvalidInput(f"A batch can hold up to {MAX_OPS} operations.")
    image = session.get(Image, image_id)
    if image is None:
        raise NotFound("That image does not exist.")
    results: list[OpResult] = []
    for op in ops:
        if op.op == "create":
            results.append(_create(session, image, op, user_id))
        elif op.op == "update":
            results.append(_update(session, image, op))
        else:
            results.append(_delete(session, image, op))
        session.flush()
    if image.status == "todo" and any(r.status == "ok" and r.annotation for r in results):
        image.status = "in_progress"
    image.updated_at = utcnow()
    session.flush()
    return results
