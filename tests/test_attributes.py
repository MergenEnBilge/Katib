import uuid
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from katib.core.attributes import AttributeError_, check_attrs, normalize_schema
from katib.db.models import Image
from katib.services import annotations, classes, projects
from katib.services.annotations import Op
from katib.services.errors import InvalidInput

SCHEMA = [
    {"name": "occluded", "type": "boolean"},
    {"name": "size", "type": "enum", "options": ["small", "large"]},
    {"name": "plate", "type": "text"},
    {"name": "speed", "type": "number"},
]


def test_schema_is_normalized_and_checked() -> None:
    out = normalize_schema([{"name": " color ", "type": "enum", "options": ["red", "blue", ""]}])
    assert out == [{"name": "color", "type": "enum", "options": ["red", "blue"]}]
    for bad in (
        [{"name": "", "type": "text"}],
        [{"name": "a", "type": "text"}, {"name": "A", "type": "text"}],
        [{"name": "a", "type": "vector"}],
        [{"name": "a", "type": "enum", "options": ["only"]}],
    ):
        with pytest.raises(AttributeError_):
            normalize_schema(bad)


@pytest.mark.parametrize(
    "attrs",
    [{"occluded": "yes"}, {"size": "medium"}, {"plate": 5}, {"speed": True}, {"speed": "fast"}],
)
def test_bad_values_are_rejected(attrs: dict[str, object]) -> None:
    with pytest.raises(AttributeError_):
        check_attrs(SCHEMA, attrs)


def test_good_and_unknown_values_pass() -> None:
    check_attrs(SCHEMA, {"occluded": True, "size": "large", "plate": "AB1", "speed": 3.5})
    check_attrs(SCHEMA, {"removed_attribute": "kept", "size": None})


def test_annotations_are_checked_against_the_class_schema(session: Session, tmp_path: Path) -> None:
    project = projects.create_project(session, "P")
    car = classes.create_class(session, project.id, "car")
    classes.set_attr_schema(session, car.id, SCHEMA)
    image = Image(
        project_id=project.id, filename="a.jpg", storage_key="k", width=10, height=10,
        sha256="x", position=0,
    )  # fmt: skip
    session.add(image)
    session.flush()
    box = {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}
    good = Op(
        "create", uuid.uuid4(), type="box", class_id=car.id, geometry=box, attrs={"size": "large"}
    )
    bad = Op(
        "create", uuid.uuid4(), type="box", class_id=car.id, geometry=box, attrs={"size": "huge"}
    )
    results = annotations.apply_batch(session, image.id, [good, bad])
    assert [r.status for r in results] == ["ok", "invalid"]
    assert "one of small, large" in (results[1].error or "")

    [upd] = annotations.apply_batch(
        session, image.id, [Op("update", good.id, patch={"attrs": {"speed": "fast"}})]
    )
    assert upd.status == "invalid"


def test_schema_change_through_the_service_validates(session: Session) -> None:
    project = projects.create_project(session, "P")
    car = classes.create_class(session, project.id, "car")
    with pytest.raises(InvalidInput):
        classes.set_attr_schema(session, car.id, [{"name": "x", "type": "nope"}])
