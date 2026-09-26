import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from katib.db.models import Class, Image, Project
from katib.services import classes, projects
from katib.services.errors import InvalidInput, NotFound, ProjectNameTaken


def test_create_and_list(session: Session) -> None:
    p = projects.create_project(session, "  Street Scenes ")
    assert p.name == "Street Scenes"
    assert p.slug == "street-scenes"
    assert p.settings["annotation_types"] == ["box", "polygon"]
    [summary] = projects.list_projects(session)
    assert summary.project.id == p.id
    assert (summary.image_count, summary.done_count) == (0, 0)


def test_names_are_unique_ignoring_case(session: Session) -> None:
    projects.create_project(session, "Cats")
    with pytest.raises(ProjectNameTaken, match="cats"):
        projects.create_project(session, "cats")


def test_slugs_stay_unique(session: Session) -> None:
    a = projects.create_project(session, "A B")
    b = projects.create_project(session, "A-B")
    assert a.slug != b.slug


@pytest.mark.parametrize("name", ["", "   ", "x" * 201])
def test_bad_names_rejected(session: Session, name: str) -> None:
    with pytest.raises(InvalidInput):
        projects.create_project(session, name)


def test_summary_counts_images(session: Session) -> None:
    p = projects.create_project(session, "P")
    for i, status in enumerate(["todo", "done", "approved"]):
        session.add(
            Image(
                project_id=p.id, filename=f"{i}.jpg", storage_key=f"k{i}", width=1, height=1,
                sha256=str(i), status=status, position=i,
            )
        )  # fmt: skip
    session.flush()
    [summary] = projects.list_projects(session)
    assert (summary.image_count, summary.done_count) == (3, 2)


def test_the_cover_is_the_first_picture(session: Session) -> None:
    p = projects.create_project(session, "P")
    assert projects.list_projects(session)[0].cover_image_id is None, "empty project has no cover"

    images = [
        Image(
            project_id=p.id, filename=f"{i}.jpg", storage_key=f"k{i}", width=1, height=1,
            sha256=str(i), position=position,
        )  # fmt: skip
        for i, position in enumerate([2, 0, 1])
    ]
    session.add_all(images)
    session.flush()

    [summary] = projects.list_projects(session)
    assert summary.cover_image_id == images[1].id, "the picture at position 0 is the cover"


def test_search_filters_by_name(session: Session) -> None:
    projects.create_project(session, "Street Scenes")
    projects.create_project(session, "Birds")
    assert [s.project.name for s in projects.list_projects(session, "bird")] == ["Birds"]


def test_rename_rejects_duplicates(session: Session) -> None:
    a = projects.create_project(session, "A")
    projects.create_project(session, "B")
    with pytest.raises(ProjectNameTaken):
        projects.rename_project(session, a.id, "b")
    assert projects.rename_project(session, a.id, "A2").name == "A2"


def test_delete_removes_project_and_its_rows(session: Session) -> None:
    p = projects.create_project(session, "P")
    classes.create_class(session, p.id, "car")
    session.commit()
    projects.delete_project(session, p.id)
    session.commit()
    assert session.scalar(select(Project).where(Project.id == p.id)) is None
    assert session.scalar(select(Class).where(Class.project_id == p.id)) is None


def test_missing_project(session: Session) -> None:
    with pytest.raises(NotFound):
        projects.get_project(session, uuid.uuid4())
