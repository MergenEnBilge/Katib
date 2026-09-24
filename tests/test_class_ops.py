import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from katib.db.base import utcnow
from katib.db.models import Annotation, Class, Image, Operation
from katib.services import class_ops, classes, projects
from katib.services.class_ops import NotRevertible
from katib.services.errors import InvalidInput
from katib.storage.local import LocalStorage


class World:
    def __init__(self, session: Session, tmp_path: Path) -> None:
        self.session = session
        self.store = LocalStorage(tmp_path / "ops")
        self.project = projects.create_project(session, "P")
        self.car = classes.create_class(session, self.project.id, "car")
        self.van = classes.create_class(session, self.project.id, "van")
        self.bus = classes.create_class(session, self.project.id, "bus")
        self.images: list[Image] = []
        for i in range(3):
            img = Image(
                project_id=self.project.id, filename=f"{i}.jpg", storage_key=f"k{i}",
                width=100, height=100, sha256=str(i), position=i,
            )  # fmt: skip
            session.add(img)
            self.images.append(img)
        session.flush()

    def shape(self, image: int, cls: Class, attrs: dict[str, object] | None = None) -> Annotation:
        ann = Annotation(
            id=uuid.uuid4(), image_id=self.images[image].id, class_id=cls.id, type="box",
            geometry={"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}, attrs=attrs or {},
        )  # fmt: skip
        self.session.add(ann)
        self.session.flush()
        return ann

    def names(self) -> list[tuple[str, int]]:
        rows = self.session.execute(
            select(Class.name, Class.position)
            .where(Class.project_id == self.project.id)
            .order_by(Class.position)
        ).all()
        return [(n, p) for n, p in rows]


@pytest.fixture
def w(session: Session, tmp_path: Path) -> World:
    return World(session, tmp_path)


def test_merge_dry_run_reports_counts_and_changes_nothing(w: World) -> None:
    w.shape(0, w.van)
    w.shape(0, w.van)
    w.shape(1, w.van)
    preview = class_ops.preview_merge(w.session, w.van.id, w.car.id)
    assert (preview.annotations, preview.images) == (3, 2)
    assert w.session.get(Class, w.van.id) is not None


def test_merge_relabels_adds_alias_and_closes_the_gap(w: World) -> None:
    anns = [w.shape(0, w.van), w.shape(1, w.van), w.shape(1, w.car)]
    result = class_ops.merge_classes(w.session, w.store, w.van.id, w.car.id)
    w.session.expire_all()
    assert result.preview.annotations == 2
    assert (
        "Merged" in result.operation.summary
        and "2 annotations on 2 images" in result.operation.summary
    )
    assert {a.class_id for a in anns} == {w.car.id}
    assert w.names() == [("car", 0), ("bus", 1)]
    assert classes.resolve_class(w.session, w.project.id, "Van").id == w.car.id  # type: ignore[union-attr]
    assert w.store.exists(result.operation.inverse_ref or "")


def test_merge_rejects_same_class(w: World) -> None:
    with pytest.raises(InvalidInput):
        class_ops.merge_classes(w.session, w.store, w.car.id, w.car.id)


def test_merge_drops_attribute_values_the_target_does_not_define(w: World) -> None:
    w.van.attr_schema = [{"name": "color", "type": "text"}, {"name": "size", "type": "text"}]
    w.car.attr_schema = [{"name": "color", "type": "text"}]
    ann = w.shape(0, w.van, {"color": "red", "size": "big"})
    preview = class_ops.preview_merge(w.session, w.van.id, w.car.id)
    assert preview.dropped_attr_values == 1
    result = class_ops.merge_classes(w.session, w.store, w.van.id, w.car.id)
    w.session.expire_all()
    assert ann.attrs == {"color": "red"}
    class_ops.revert(w.session, w.store, result.operation.id)
    w.session.expire_all()
    assert ann.attrs == {"color": "red", "size": "big"}


def test_revert_merge_restores_class_position_and_annotations(w: World) -> None:
    anns = [w.shape(0, w.van), w.shape(1, w.van)]
    result = class_ops.merge_classes(w.session, w.store, w.van.id, w.car.id)
    outcome = class_ops.revert(w.session, w.store, result.operation.id)
    w.session.expire_all()
    assert (outcome.restored, outcome.skipped) == (2, 0)
    assert w.names() == [("car", 0), ("van", 1), ("bus", 2)]
    assert {a.class_id for a in anns} == {w.van.id}
    assert classes.resolve_class(w.session, w.project.id, "van").id == w.van.id  # type: ignore[union-attr]


def test_revert_skips_annotations_edited_since(w: World) -> None:
    a, b = w.shape(0, w.van), w.shape(1, w.van)
    result = class_ops.merge_classes(w.session, w.store, w.van.id, w.car.id)
    w.session.flush()
    edited = w.session.get(Annotation, b.id)
    assert edited is not None
    edited.updated_at = utcnow() + timedelta(seconds=5)
    w.session.flush()
    outcome = class_ops.revert(w.session, w.store, result.operation.id)
    w.session.expire_all()
    assert (outcome.restored, outcome.skipped) == (1, 1)
    assert a.class_id == w.van.id and b.class_id == w.car.id


def test_revert_only_once_and_needs_a_free_name(w: World) -> None:
    w.shape(0, w.van)
    result = class_ops.merge_classes(w.session, w.store, w.van.id, w.car.id)
    classes.create_class(w.session, w.project.id, "van")
    with pytest.raises(NotRevertible, match="exists again"):
        class_ops.revert(w.session, w.store, result.operation.id)


def test_delete_class_removes_annotations_and_can_be_reverted(w: World) -> None:
    w.shape(0, w.van)
    w.shape(2, w.van)
    keep = w.shape(1, w.car)
    assert class_ops.preview_delete(w.session, w.van.id).annotations == 2
    result = class_ops.delete_class(w.session, w.store, w.van.id)
    assert w.session.scalars(select(Annotation)).all() == [keep]
    assert w.names() == [("car", 0), ("bus", 1)]
    outcome = class_ops.revert(w.session, w.store, result.operation.id)
    assert (outcome.restored, outcome.skipped) == (2, 0)
    assert w.names() == [("car", 0), ("van", 1), ("bus", 2)]
    assert len(w.session.scalars(select(Annotation)).all()) == 3
    with pytest.raises(NotRevertible, match="already"):
        class_ops.revert(w.session, w.store, result.operation.id)


def test_bulk_reclass_and_revert(w: World) -> None:
    a, b = w.shape(0, w.car), w.shape(1, w.car)
    result = class_ops.bulk_reclass(w.session, w.store, w.project.id, [a.id, b.id], w.bus.id)
    w.session.expire_all()
    assert {a.class_id, b.class_id} == {w.bus.id}
    assert a.version == 2
    class_ops.revert(w.session, w.store, result.operation.id)
    w.session.expire_all()
    assert {a.class_id, b.class_id} == {w.car.id}


def test_bulk_delete_and_revert(w: World) -> None:
    a, b = w.shape(0, w.car), w.shape(1, w.car)
    result = class_ops.bulk_delete(w.session, w.store, w.project.id, [a.id])
    assert w.session.get(Annotation, a.id) is None and w.session.get(Annotation, b.id) is not None
    class_ops.revert(w.session, w.store, result.operation.id)
    assert w.session.get(Annotation, a.id) is not None


def test_bulk_rejects_missing_ids(w: World) -> None:
    with pytest.raises(InvalidInput):
        class_ops.bulk_delete(w.session, w.store, w.project.id, [uuid.uuid4()])
    with pytest.raises(InvalidInput):
        class_ops.bulk_delete(w.session, w.store, w.project.id, [])


def test_history_lists_newest_first_and_expired_files_are_purged(w: World) -> None:
    w.shape(0, w.van)
    first = class_ops.merge_classes(w.session, w.store, w.van.id, w.car.id)
    second = class_ops.delete_class(w.session, w.store, w.bus.id)
    listed = class_ops.list_operations(w.session, w.project.id)
    assert [o.id for o in listed] == [second.operation.id, first.operation.id]

    first_op = w.session.get(Operation, first.operation.id)
    assert first_op is not None
    first_op.created_at = utcnow() - timedelta(days=40)
    w.session.flush()
    assert class_ops.purge_expired(w.session, w.store, 30) == 1
    with pytest.raises(NotRevertible, match="no longer"):
        class_ops.revert(w.session, w.store, first.operation.id)
    class_ops.revert(w.session, w.store, second.operation.id)


def test_merge_scales_as_one_update(w: World) -> None:
    """A merge must not load or touch rows one by one, so it stays fast on large projects."""
    for i in range(300):
        w.shape(i % 3, w.van)
    statements: list[str] = []
    from sqlalchemy import event

    @event.listens_for(w.session.get_bind(), "before_cursor_execute")
    def _capture(conn, cursor, statement, params, context, executemany) -> None:  # type: ignore[no-untyped-def]
        statements.append(statement)

    class_ops.merge_classes(w.session, w.store, w.van.id, w.car.id)
    updates = [s for s in statements if s.startswith("UPDATE annotations")]
    assert len(updates) == 1
