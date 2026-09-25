"""Class operations: merge, delete with all annotations, bulk reclass and delete, and revert.

Each destructive action runs in one transaction, supports a dry run that returns counts, and
writes an `operations` row whose inverse is a compressed JSON file (ARCHITECTURE.md section 8).
Annotations are only ever touched through `class_id`, so a merge over a million rows is one
UPDATE statement.
"""

import gzip
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import CursorResult, Result
from sqlalchemy.orm import Session

from katib.db.base import utcnow
from katib.db.models import Annotation, Class, ClassAlias, Image, Operation
from katib.services.errors import InvalidInput, KatibError, NotFound
from katib.storage.local import LocalStorage

INSERT_CHUNK = 1000


class NotRevertible(KatibError):
    code = "not_revertible"
    status = 409


@dataclass(frozen=True)
class Preview:
    annotations: int
    images: int
    dropped_attr_values: int = 0


@dataclass(frozen=True)
class OperationResult:
    operation: Operation
    preview: Preview


@dataclass(frozen=True)
class RevertResult:
    restored: int
    skipped: int


def _rows(result: Result[Any]) -> int:
    """Rows changed by an UPDATE or DELETE."""
    return cast("CursorResult[Any]", result).rowcount or 0


def _class(session: Session, class_id: uuid.UUID) -> Class:
    cls = session.get(Class, class_id)
    if cls is None:
        raise NotFound("That class does not exist.")
    return cls


def _counts(session: Session, class_id: uuid.UUID) -> tuple[int, int]:
    annotations = session.scalar(
        select(func.count(Annotation.id)).where(Annotation.class_id == class_id)
    )
    images = session.scalar(
        select(func.count(func.distinct(Annotation.image_id))).where(
            Annotation.class_id == class_id
        )
    )
    return annotations or 0, images or 0


def _schema_names(cls: Class) -> set[str]:
    names: set[str] = set()
    for item in cls.attr_schema:
        entry = cast("dict[str, Any]", item)
        if "name" in entry:
            names.add(str(entry["name"]))
    return names


def _write_inverse(storage: LocalStorage, op_id: uuid.UUID, payload: dict[str, Any]) -> str:
    key = f"{op_id}.json.gz"
    path = storage.path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(payload, fh, default=str)
    return key


def _read_inverse(storage: LocalStorage, key: str) -> dict[str, Any]:
    with gzip.open(storage.path(key), "rt", encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def _class_row(cls: Class) -> dict[str, Any]:
    return {
        "id": str(cls.id),
        "project_id": str(cls.project_id),
        "name": cls.name,
        "color": cls.color,
        "position": cls.position,
        "attr_schema": cls.attr_schema,
    }


def _annotation_row(a: Annotation) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "image_id": str(a.image_id),
        "class_id": str(a.class_id) if a.class_id else None,
        "type": a.type,
        "geometry": a.geometry,
        "attrs": a.attrs,
        "source": a.source,
        "confidence": a.confidence,
        "created_by": str(a.created_by) if a.created_by else None,
        "created_at": a.created_at.isoformat(),
        "version": a.version,
    }


def _close_gap(session: Session, project_id: uuid.UUID, position: int) -> None:
    session.execute(
        update(Class)
        .where(Class.project_id == project_id, Class.position > position)
        .values(position=Class.position - 1)
    )


def record(
    session: Session,
    storage: LocalStorage,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None,
    kind: str,
    summary: str,
    inverse: dict[str, Any],
) -> Operation:
    """Write an operation to the log with the data needed to undo it."""
    return _log(session, storage, project_id, user_id, kind, summary, inverse)


def _log(
    session: Session,
    storage: LocalStorage,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None,
    kind: str,
    summary: str,
    inverse: dict[str, Any],
) -> Operation:
    op = Operation(project_id=project_id, user_id=user_id, kind=kind, summary=summary)
    session.add(op)
    session.flush()
    op.inverse_ref = _write_inverse(storage, op.id, inverse)
    session.flush()
    return op


def _plural(n: int, one: str) -> str:
    return f"{n:,} {one}" if n == 1 else f"{n:,} {one}s"


def _dropped_values(session: Session, source: Class, target: Class) -> int:
    """Attribute values on `source` annotations that `target` does not define."""
    names = _schema_names(source)
    kept = _schema_names(target)
    doomed = names - kept
    if not doomed:
        return 0
    total = 0
    rows = session.execute(
        select(Annotation.attrs).where(Annotation.class_id == source.id)
    ).yield_per(5000)
    for (attrs,) in rows:
        total += sum(1 for key in doomed if key in attrs)
    return total


def preview_merge(session: Session, source_id: uuid.UUID, target_id: uuid.UUID) -> Preview:
    source, target = _class(session, source_id), _class(session, target_id)
    _check_merge(source, target)
    annotations, images = _counts(session, source.id)
    return Preview(annotations, images, _dropped_values(session, source, target))


def _check_merge(source: Class, target: Class) -> None:
    if source.id == target.id:
        raise InvalidInput("Choose a different class to merge into.")
    if source.project_id != target.project_id:
        raise InvalidInput("Both classes must be in the same project.")


def merge_classes(
    session: Session,
    storage: LocalStorage,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> OperationResult:
    """Relabel every annotation of `source` as `target` and remove `source`."""
    source, target = _class(session, source_id), _class(session, target_id)
    _check_merge(source, target)
    preview = Preview(*_counts(session, source.id), _dropped_values(session, source, target))

    moved_ids = [
        str(i)
        for i in session.scalars(select(Annotation.id).where(Annotation.class_id == source.id))
    ]
    original_attrs: dict[str, dict[str, Any]] = {}
    doomed = _schema_names(source) - _schema_names(target)
    if doomed:
        rows = session.execute(
            select(Annotation.id, Annotation.attrs).where(Annotation.class_id == source.id)
        ).all()
        for ann_id, attrs in rows:
            if any(key in attrs for key in doomed):
                original_attrs[str(ann_id)] = dict(attrs)
                kept = {k: v for k, v in attrs.items() if k not in doomed}
                session.execute(
                    update(Annotation).where(Annotation.id == ann_id).values(attrs=kept)
                )

    session.execute(
        update(Annotation).where(Annotation.class_id == source.id).values(class_id=target.id)
    )
    alias = source.name.lower()
    if session.get(ClassAlias, (source.project_id, alias)) is None:
        session.add(ClassAlias(project_id=source.project_id, alias=alias, class_id=target.id))
    # Aliases that pointed at the old class now point at the target.
    session.execute(
        update(ClassAlias).where(ClassAlias.class_id == source.id).values(class_id=target.id)
    )
    inverse_class = _class_row(source)
    session.flush()
    session.delete(source)
    session.flush()
    _close_gap(session, source.project_id, inverse_class["position"])

    summary = (
        f"Merged “{source.name}” into “{target.name}”: "
        f"{_plural(preview.annotations, 'annotation')} on {_plural(preview.images, 'image')}."
    )
    op = _log(
        session,
        storage,
        target.project_id,
        user_id,
        "merge_classes",
        summary,
        {
            "class": inverse_class,
            "target_id": str(target.id),
            "alias": alias,
            "moved": moved_ids,
            "original_attrs": original_attrs,
        },
    )
    return OperationResult(op, preview)


def preview_delete(session: Session, class_id: uuid.UUID) -> Preview:
    cls = _class(session, class_id)
    return Preview(*_counts(session, cls.id))


def delete_class(
    session: Session,
    storage: LocalStorage,
    class_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> OperationResult:
    """Delete a class and every annotation that uses it."""
    cls = _class(session, class_id)
    preview = Preview(*_counts(session, cls.id))
    rows = [
        _annotation_row(a)
        for a in session.scalars(select(Annotation).where(Annotation.class_id == cls.id)).yield_per(
            2000
        )
    ]
    aliases = [
        a.alias for a in session.scalars(select(ClassAlias).where(ClassAlias.class_id == cls.id))
    ]
    inverse_class = _class_row(cls)
    session.execute(delete(Annotation).where(Annotation.class_id == cls.id))
    session.execute(delete(ClassAlias).where(ClassAlias.class_id == cls.id))
    session.delete(cls)
    session.flush()
    _close_gap(session, cls.project_id, inverse_class["position"])
    summary = (
        f"Deleted “{cls.name}” and {_plural(preview.annotations, 'annotation')} "
        f"on {_plural(preview.images, 'image')}."
    )
    op = _log(
        session,
        storage,
        cls.project_id,
        user_id,
        "delete_class",
        summary,
        {"class": inverse_class, "annotations": rows, "aliases": aliases},
    )
    return OperationResult(op, preview)


def _selected(session: Session, project_id: uuid.UUID, ids: list[uuid.UUID]) -> list[Annotation]:
    if not ids:
        raise InvalidInput("Select at least one annotation.")
    found = list(
        session.scalars(
            select(Annotation)
            .join(Image, Image.id == Annotation.image_id)
            .where(Annotation.id.in_(ids), Image.project_id == project_id)
        )
    )
    if len(found) != len(set(ids)):
        raise InvalidInput("Some of those annotations no longer exist.")
    return found


def preview_bulk(session: Session, project_id: uuid.UUID, ids: list[uuid.UUID]) -> Preview:
    found = _selected(session, project_id, ids)
    return Preview(len(found), len({a.image_id for a in found}))


def bulk_reclass(
    session: Session,
    storage: LocalStorage,
    project_id: uuid.UUID,
    ids: list[uuid.UUID],
    target_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> OperationResult:
    target = _class(session, target_id)
    if target.project_id != project_id:
        raise InvalidInput("That class does not belong to this project.")
    found = _selected(session, project_id, ids)
    preview = Preview(len(found), len({a.image_id for a in found}))
    before = {str(a.id): str(a.class_id) for a in found}
    for chunk_start in range(0, len(found), INSERT_CHUNK):
        chunk = [a.id for a in found[chunk_start : chunk_start + INSERT_CHUNK]]
        session.execute(
            update(Annotation)
            .where(Annotation.id.in_(chunk))
            .values(class_id=target.id, version=Annotation.version + 1, updated_at=utcnow())
        )
    summary = (
        f"Relabeled {_plural(preview.annotations, 'annotation')} on "
        f"{_plural(preview.images, 'image')} as “{target.name}”."
    )
    op = _log(session, storage, project_id, user_id, "bulk_reclass", summary, {"before": before})
    return OperationResult(op, preview)


def bulk_delete(
    session: Session,
    storage: LocalStorage,
    project_id: uuid.UUID,
    ids: list[uuid.UUID],
    user_id: uuid.UUID | None = None,
) -> OperationResult:
    found = _selected(session, project_id, ids)
    preview = Preview(len(found), len({a.image_id for a in found}))
    rows = [_annotation_row(a) for a in found]
    for a in found:
        session.delete(a)
    session.flush()
    summary = (
        f"Deleted {_plural(preview.annotations, 'annotation')} "
        f"on {_plural(preview.images, 'image')}."
    )
    op = _log(session, storage, project_id, user_id, "bulk_delete", summary, {"annotations": rows})
    return OperationResult(op, preview)


def list_operations(session: Session, project_id: uuid.UUID, limit: int = 50) -> list[Operation]:
    return list(
        session.scalars(
            select(Operation)
            .where(Operation.project_id == project_id)
            .order_by(Operation.created_at.desc(), Operation.id.desc())
            .limit(limit)
        )
    )


def _restore_annotations(session: Session, rows: list[dict[str, Any]]) -> tuple[int, int]:
    restored = skipped = 0
    for row in rows:
        image_ok = session.get(Image, uuid.UUID(row["image_id"])) is not None
        if not image_ok or session.get(Annotation, uuid.UUID(row["id"])) is not None:
            skipped += 1
            continue
        session.add(
            Annotation(
                id=uuid.UUID(row["id"]),
                image_id=uuid.UUID(row["image_id"]),
                class_id=uuid.UUID(row["class_id"]) if row["class_id"] else None,
                type=row["type"],
                geometry=row["geometry"],
                attrs=row["attrs"],
                source=row["source"],
                confidence=row["confidence"],
                created_by=uuid.UUID(row["created_by"]) if row["created_by"] else None,
                version=row["version"],
            )
        )
        restored += 1
    return restored, skipped


def _restore_class(session: Session, data: dict[str, Any]) -> Class:
    project_id = uuid.UUID(data["project_id"])
    session.execute(
        update(Class)
        .where(Class.project_id == project_id, Class.position >= data["position"])
        .values(position=Class.position + 1)
    )
    cls = Class(
        id=uuid.UUID(data["id"]),
        project_id=project_id,
        name=data["name"],
        color=data["color"],
        position=data["position"],
        attr_schema=data["attr_schema"],
    )
    session.add(cls)
    session.flush()
    return cls


def revert(session: Session, storage: LocalStorage, operation_id: uuid.UUID) -> RevertResult:
    """Undo an operation as far as possible. Annotations edited since are skipped and counted."""
    op = session.get(Operation, operation_id)
    if op is None:
        raise NotFound("That operation does not exist.")
    if op.reverted_at is not None:
        raise NotRevertible("This has already been undone.")
    if not op.inverse_ref or not storage.exists(op.inverse_ref):
        raise NotRevertible("This can no longer be undone. Undo is kept for a limited time.")
    data = _read_inverse(storage, op.inverse_ref)

    if op.kind == "merge_classes":
        result = _revert_merge(session, op, data)
    elif op.kind == "delete_class":
        cls = data["class"]
        if session.get(Class, uuid.UUID(cls["id"])) is not None:
            raise NotRevertible("That class already exists again.")
        _restore_class(session, cls)
        for alias in data["aliases"]:
            if session.get(ClassAlias, (uuid.UUID(cls["project_id"]), alias)) is None:
                session.add(
                    ClassAlias(
                        project_id=uuid.UUID(cls["project_id"]),
                        alias=alias,
                        class_id=uuid.UUID(cls["id"]),
                    )
                )
        restored, skipped = _restore_annotations(session, data["annotations"])
        result = RevertResult(restored, skipped)
    elif op.kind == "bulk_reclass":
        result = _revert_reclass(session, op, data)
    elif op.kind == "bulk_delete":
        restored, skipped = _restore_annotations(session, data["annotations"])
        result = RevertResult(restored, skipped)
    elif op.kind == "prelabel":
        result = _revert_prelabel(session, op, data)
    elif op.kind == "shuffle_splits":
        result = RevertResult(_restore_splits(session, data), 0)
    else:
        raise NotRevertible("This kind of operation cannot be undone.")

    op.reverted_at = utcnow()
    session.flush()
    return result


def _revert_merge(session: Session, op: Operation, data: dict[str, Any]) -> RevertResult:
    cls = data["class"]
    project_id = uuid.UUID(cls["project_id"])
    if session.scalar(
        select(Class.id).where(
            Class.project_id == project_id, func.lower(Class.name) == cls["name"].lower()
        )
    ):
        raise NotRevertible(
            f"A class named “{cls['name']}” exists again, so it cannot be restored."
        )
    if session.get(Class, uuid.UUID(data["target_id"])) is None:
        raise NotRevertible("The class it was merged into no longer exists.")
    restored_class = _restore_class(session, cls)
    session.execute(
        delete(ClassAlias).where(
            ClassAlias.project_id == project_id, ClassAlias.alias == data["alias"]
        )
    )
    moved = [uuid.UUID(i) for i in data["moved"]]
    restored = 0
    for start in range(0, len(moved), INSERT_CHUNK):
        chunk = moved[start : start + INSERT_CHUNK]
        # Rows edited after the merge have a newer updated_at and are left where they are.
        result = session.execute(
            update(Annotation)
            .where(
                Annotation.id.in_(chunk),
                Annotation.class_id == uuid.UUID(data["target_id"]),
                Annotation.updated_at <= op.created_at,
            )
            .values(class_id=restored_class.id)
        )
        restored += _rows(result)
    for ann_id, attrs in data["original_attrs"].items():
        session.execute(
            update(Annotation)
            .where(Annotation.id == uuid.UUID(ann_id), Annotation.class_id == restored_class.id)
            .values(attrs=attrs)
        )
    return RevertResult(restored, len(moved) - restored)


def _restore_splits(session: Session, data: dict[str, Any]) -> int:
    before: dict[str, str | None] = data["before"]
    ids_by_split: dict[str | None, list[uuid.UUID]] = {}
    for image_id, name in before.items():
        ids_by_split.setdefault(name, []).append(uuid.UUID(image_id))
    for name, ids in ids_by_split.items():
        for start in range(0, len(ids), INSERT_CHUNK):
            session.execute(
                update(Image)
                .where(Image.id.in_(ids[start : start + INSERT_CHUNK]))
                .values(split=name, version=Image.version + 1)
            )
    return len(before)


def _revert_prelabel(session: Session, op: Operation, data: dict[str, Any]) -> RevertResult:
    """Remove the shapes a model added, except ones someone has edited since."""
    ids = [uuid.UUID(i) for i in data["annotation_ids"]]
    removed = 0
    for start in range(0, len(ids), INSERT_CHUNK):
        result = session.execute(
            delete(Annotation).where(
                Annotation.id.in_(ids[start : start + INSERT_CHUNK]),
                Annotation.updated_at <= op.created_at,
            )
        )
        removed += _rows(result)
    return RevertResult(removed, len(ids) - removed)


def _revert_reclass(session: Session, op: Operation, data: dict[str, Any]) -> RevertResult:
    restored = 0
    before: dict[str, str] = data["before"]
    for ann_id, class_id in before.items():
        result = session.execute(
            update(Annotation)
            .where(Annotation.id == uuid.UUID(ann_id), Annotation.updated_at <= op.created_at)
            .values(class_id=uuid.UUID(class_id), version=Annotation.version + 1)
        )
        restored += _rows(result)
    return RevertResult(restored, len(before) - restored)


def purge_expired(
    session: Session, storage: LocalStorage, retention_days: int, now: datetime | None = None
) -> int:
    """Delete inverse files past the retention window. Those operations cannot be undone."""
    cutoff = (now or utcnow()) - timedelta(days=retention_days)
    ops = session.scalars(
        select(Operation).where(Operation.created_at < cutoff, Operation.inverse_ref.is_not(None))
    )
    count = 0
    for op in ops:
        if op.inverse_ref:
            storage.delete(op.inverse_ref)
            op.inverse_ref = None
            count += 1
    session.flush()
    return count
