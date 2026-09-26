"""Projects: create, list, rename, delete."""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from katib.db.models import Image, Project, ProjectMember
from katib.services.errors import InvalidInput, NotFound, ProjectNameTaken

DEFAULT_TYPES = ["box", "polygon"]
MAX_NAME = 200


@dataclass(frozen=True)
class ProjectSummary:
    project: Project
    image_count: int
    done_count: int
    last_edited: datetime | None
    #: The first picture, shown on the project card. None while a project is empty.
    cover_image_id: uuid.UUID | None = None


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


def _clean_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise InvalidInput("Give the project a name.")
    if len(name) > MAX_NAME:
        raise InvalidInput(f"Project names can be up to {MAX_NAME} characters.")
    return name


def _name_taken(session: Session, name: str, exclude: uuid.UUID | None = None) -> bool:
    stmt = select(Project.id).where(func.lower(Project.name) == name.lower())
    if exclude is not None:
        stmt = stmt.where(Project.id != exclude)
    return session.scalar(stmt.limit(1)) is not None


def _unique_slug(session: Session, name: str) -> str:
    base = slugify(name)
    slug, n = base, 2
    while session.scalar(select(Project.id).where(Project.slug == slug)) is not None:
        slug = f"{base}-{n}"
        n += 1
    return slug


def create_project(
    session: Session,
    name: str,
    annotation_types: list[str] | None = None,
    created_by: uuid.UUID | None = None,
) -> Project:
    name = _clean_name(name)
    if _name_taken(session, name):
        raise ProjectNameTaken(f"A project named “{name}” already exists.")
    types = annotation_types or DEFAULT_TYPES
    settings: dict[str, Any] = {"annotation_types": types, "review_enabled": False}
    project = Project(
        name=name, slug=_unique_slug(session, name), settings=settings, created_by=created_by
    )
    session.add(project)
    session.flush()
    if created_by is not None:
        session.add(ProjectMember(project_id=project.id, user_id=created_by, role="owner"))
        session.flush()
    return project


def get_project(session: Session, project_id: uuid.UUID) -> Project:
    project = session.get(Project, project_id)
    if project is None or project.archived_at is not None:
        raise NotFound("That project does not exist.")
    return project


def list_projects(
    session: Session, query: str | None = None, visible: set[uuid.UUID] | None = None
) -> list[ProjectSummary]:
    """Projects with counts. `visible` limits the list to those ids, None means all."""
    cover = (
        select(Image.id)
        .where(Image.project_id == Project.id)
        .order_by(Image.position)
        .limit(1)
        .correlate(Project)
        .scalar_subquery()
    )
    stmt = (
        select(
            Project,
            func.count(Image.id),
            func.count(Image.id).filter(Image.status.in_(("done", "approved"))),
            func.max(Image.updated_at),
            cover,
        )
        .outerjoin(Image, Image.project_id == Project.id)
        .where(Project.archived_at.is_(None))
        .group_by(Project.id)
        .order_by(Project.created_at.desc())
    )
    if visible is not None:
        stmt = stmt.where(Project.id.in_(visible))
    if query:
        stmt = stmt.where(func.lower(Project.name).contains(query.lower()))
    return [
        ProjectSummary(p, images, done, last, cover_id)
        for p, images, done, last, cover_id in session.execute(stmt).all()
    ]


def rename_project(session: Session, project_id: uuid.UUID, name: str) -> Project:
    project = get_project(session, project_id)
    name = _clean_name(name)
    if _name_taken(session, name, exclude=project.id):
        raise ProjectNameTaken(f"A project named “{name}” already exists.")
    project.name = name
    session.flush()
    return project


def delete_project(session: Session, project_id: uuid.UUID) -> None:
    """Delete the project and its rows. Referenced image files on disk are never touched."""
    project = get_project(session, project_id)
    session.delete(project)
    session.flush()
