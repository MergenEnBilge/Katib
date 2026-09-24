import uuid

import pytest
from sqlalchemy.orm import Session

from katib.core.palette import DEFAULT_PALETTE, next_color
from katib.services import classes, projects
from katib.services.errors import ClassNameTaken, InvalidInput, NotFound


@pytest.fixture
def pid(session: Session) -> uuid.UUID:
    return projects.create_project(session, "P").id


def test_new_classes_get_palette_colors_and_positions(session: Session, pid: uuid.UUID) -> None:
    a = classes.create_class(session, pid, "car")
    b = classes.create_class(session, pid, "bus")
    assert (a.color, b.color) == (DEFAULT_PALETTE[0], DEFAULT_PALETTE[1])
    assert (a.position, b.position) == (0, 1)


def test_duplicate_names_rejected_ignoring_case(session: Session, pid: uuid.UUID) -> None:
    classes.create_class(session, pid, "Car")
    with pytest.raises(ClassNameTaken) as err:
        classes.create_class(session, pid, "car")
    assert "already exists" in err.value.message


def test_rename_keeps_old_name_as_alias(session: Session, pid: uuid.UUID) -> None:
    c = classes.create_class(session, pid, "automobile")
    classes.rename_class(session, c.id, "car")
    assert classes.resolve_class(session, pid, "Automobile") is not None
    assert classes.resolve_class(session, pid, "automobile").id == c.id  # type: ignore[union-attr]
    assert classes.resolve_class(session, pid, "car").id == c.id  # type: ignore[union-attr]


def test_rename_to_taken_name_rejected(session: Session, pid: uuid.UUID) -> None:
    classes.create_class(session, pid, "car")
    b = classes.create_class(session, pid, "bus")
    with pytest.raises(ClassNameTaken):
        classes.rename_class(session, b.id, "CAR")


def test_new_class_reclaims_an_alias_name(session: Session, pid: uuid.UUID) -> None:
    old = classes.create_class(session, pid, "van")
    classes.rename_class(session, old.id, "minivan")
    fresh = classes.create_class(session, pid, "van")
    assert classes.resolve_class(session, pid, "van").id == fresh.id  # type: ignore[union-attr]


def test_recolor_validates(session: Session, pid: uuid.UUID) -> None:
    c = classes.create_class(session, pid, "car")
    assert classes.recolor_class(session, c.id, "#abcdef").color == "#ABCDEF"
    with pytest.raises(InvalidInput):
        classes.recolor_class(session, c.id, "red")


def test_reorder(session: Session, pid: uuid.UUID) -> None:
    a = classes.create_class(session, pid, "a")
    b = classes.create_class(session, pid, "b")
    classes.reorder_classes(session, pid, [b.id, a.id])
    assert [c.cls.name for c in classes.list_classes(session, pid)] == ["b", "a"]
    with pytest.raises(InvalidInput):
        classes.reorder_classes(session, pid, [a.id])


def test_missing_class(session: Session) -> None:
    with pytest.raises(NotFound):
        classes.get_class(session, uuid.uuid4())


def test_palette_generates_distinct_colors_past_ten() -> None:
    used = list(DEFAULT_PALETTE)
    for _ in range(15):
        used.append(next_color(used))
    assert len(set(c.lower() for c in used)) == 25
