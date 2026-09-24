import uuid
from pathlib import Path

import pytest
from PIL import Image as PILImage
from sqlalchemy import select
from sqlalchemy.orm import Session

from katib.db.models import Annotation, Image
from katib.services import annotations, classes, images, projects
from katib.services.annotations import Op
from katib.services.errors import NotFound
from katib.services.images import StorageContext
from katib.storage.local import LocalStorage

BOX = {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.3}


class Setup:
    def __init__(self, session: Session, tmp_path: Path) -> None:
        lib = tmp_path / "lib"
        lib.mkdir()
        PILImage.new("RGB", (50, 40), "red").save(lib / "a.png")
        ctx = StorageContext(
            LocalStorage(tmp_path / "u"), LocalStorage(tmp_path / "t"), [lib], 1_000_000
        )
        self.project = projects.create_project(session, "P")
        images.import_folder(session, self.project.id, str(lib), ctx)
        self.image = session.scalars(select(Image)).one()
        self.car = classes.create_class(session, self.project.id, "car")
        self.bus = classes.create_class(session, self.project.id, "bus")


@pytest.fixture
def s(session: Session, tmp_path: Path) -> Setup:
    return Setup(session, tmp_path)


def create(s: Setup, **kw) -> Op:  # type: ignore[no-untyped-def]
    return Op(
        "create",
        kw.pop("id", uuid.uuid4()),
        type=kw.pop("type", "box"),
        class_id=kw.pop("class_id", s.car.id),
        geometry=kw.pop("geometry", BOX),
        **kw,
    )


def test_create_stores_shape_and_moves_image_to_in_progress(session: Session, s: Setup) -> None:
    [r] = annotations.apply_batch(session, s.image.id, [create(s)])
    assert r.status == "ok"
    assert r.annotation is not None and r.annotation.version == 1
    assert s.image.status == "in_progress"
    assert len(annotations.list_annotations(session, s.image.id)) == 1


def test_create_is_idempotent(session: Session, s: Setup) -> None:
    op = create(s)
    annotations.apply_batch(session, s.image.id, [op])
    annotations.apply_batch(session, s.image.id, [op])
    assert len(annotations.list_annotations(session, s.image.id)) == 1


def test_invalid_geometry_and_class_are_reported_not_raised(session: Session, s: Setup) -> None:
    bad_geo = create(s, geometry={"x": 0.9, "y": 0.9, "w": 0.5, "h": 0.5})
    bad_class = create(s, class_id=uuid.uuid4())
    good = create(s)
    results = annotations.apply_batch(session, s.image.id, [bad_geo, bad_class, good])
    assert [r.status for r in results] == ["invalid", "invalid", "ok"]
    assert "edge" in (results[0].error or "")
    assert len(annotations.list_annotations(session, s.image.id)) == 1


def test_update_bumps_version_and_conflicts_on_stale_version(session: Session, s: Setup) -> None:
    op = create(s)
    annotations.apply_batch(session, s.image.id, [op])
    moved = {"x": 0.5, "y": 0.5, "w": 0.1, "h": 0.1}
    [ok] = annotations.apply_batch(
        session, s.image.id, [Op("update", op.id, if_version=1, patch={"geometry": moved})]
    )
    assert ok.status == "ok" and ok.annotation is not None
    assert ok.annotation.version == 2
    assert ok.annotation.geometry["x"] == 0.5

    [stale] = annotations.apply_batch(
        session, s.image.id, [Op("update", op.id, if_version=1, patch={"class_id": str(s.bus.id)})]
    )
    assert stale.status == "conflict"
    assert stale.annotation is not None and stale.annotation.class_id == s.car.id


def test_reclass_via_update(session: Session, s: Setup) -> None:
    op = create(s)
    annotations.apply_batch(session, s.image.id, [op])
    [r] = annotations.apply_batch(
        session, s.image.id, [Op("update", op.id, patch={"class_id": str(s.bus.id)})]
    )
    assert r.annotation is not None and r.annotation.class_id == s.bus.id


def test_update_rejects_unknown_fields_and_bad_geometry(session: Session, s: Setup) -> None:
    op = create(s)
    annotations.apply_batch(session, s.image.id, [op])
    [a, b] = annotations.apply_batch(
        session,
        s.image.id,
        [
            Op("update", op.id, patch={"type": "polygon"}),
            Op("update", op.id, patch={"geometry": {"x": 2}}),
        ],
    )
    assert (a.status, b.status) == ("invalid", "invalid")


def test_delete_and_missing_delete_are_both_ok(session: Session, s: Setup) -> None:
    op = create(s)
    annotations.apply_batch(session, s.image.id, [op])
    results = annotations.apply_batch(
        session, s.image.id, [Op("delete", op.id), Op("delete", op.id)]
    )
    assert [r.status for r in results] == ["ok", "ok"]
    assert session.scalars(select(Annotation)).all() == []


def test_update_of_missing_shape_is_not_found(session: Session, s: Setup) -> None:
    [r] = annotations.apply_batch(session, s.image.id, [Op("update", uuid.uuid4(), patch={})])
    assert r.status == "not_found"


def test_disabled_type_is_rejected(session: Session, s: Setup) -> None:
    s.project.settings = {"annotation_types": ["box"]}
    session.flush()
    poly = create(s, type="polygon", geometry={"points": [[0.1, 0.1], [0.4, 0.1], [0.2, 0.5]]})
    [r] = annotations.apply_batch(session, s.image.id, [poly])
    assert r.status == "invalid"


def test_polygon_round_trip(session: Session, s: Setup) -> None:
    pts = [[0.1, 0.1], [0.4, 0.1], [0.2, 0.5]]
    poly = create(s, type="polygon", geometry={"points": pts})
    annotations.apply_batch(session, s.image.id, [poly])
    [ann] = annotations.list_annotations(session, s.image.id)
    assert ann.geometry["points"] == [tuple(p) for p in pts] or ann.geometry["points"] == pts


def test_unknown_image(session: Session) -> None:
    with pytest.raises(NotFound):
        annotations.apply_batch(session, uuid.uuid4(), [])


def test_partly_invalid_patch_changes_nothing(session: Session, s: Setup) -> None:
    op = create(s)
    annotations.apply_batch(session, s.image.id, [op])
    [r] = annotations.apply_batch(
        session,
        s.image.id,
        [Op("update", op.id, patch={"class_id": str(s.bus.id), "geometry": {"x": 9}})],
    )
    assert r.status == "invalid"
    [ann] = annotations.list_annotations(session, s.image.id)
    assert ann.class_id == s.car.id and ann.version == 1
