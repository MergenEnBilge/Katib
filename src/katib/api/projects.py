"""Project routes."""

import uuid

from fastapi import APIRouter, Response
from sqlalchemy.orm import Session

from katib.api.deps import SessionDep, StorageDep, UserDep, need
from katib.api.schemas import ProjectIn, ProjectOut, ProjectPatch
from katib.db.models import User
from katib.services import access, projects, samples, tasks
from katib.services.errors import NotFound
from katib.services.projects import ProjectSummary

router = APIRouter(tags=["projects"])


def _out(s: ProjectSummary, role: str = "owner") -> ProjectOut:
    p = s.project
    return ProjectOut(
        review_enabled=bool(p.settings.get("review_enabled")),
        role=role,
        id=p.id,
        name=p.name,
        slug=p.slug,
        annotation_types=list(p.settings.get("annotation_types", [])),
        image_count=s.image_count,
        done_count=s.done_count,
        created_at=p.created_at,
        last_edited=s.last_edited,
        cover_image_id=s.cover_image_id,
    )


def _one(session: Session, project_id: uuid.UUID, user: User) -> ProjectOut:
    for s in projects.list_projects(session):
        if s.project.id == project_id:
            return _out(s, access.role_of(session, user, project_id) or "viewer")
    raise NotFound("That project does not exist.")


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(session: SessionDep, user: UserDep, q: str | None = None) -> list[ProjectOut]:
    visible = access.visible_project_ids(session, user)
    return [
        _out(s, access.role_of(session, user, s.project.id) or "viewer")
        for s in projects.list_projects(session, q, visible)
    ]


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, session: SessionDep, user: UserDep) -> ProjectOut:
    types: list[str] | None = [str(t) for t in body.annotation_types or []] or None
    p = projects.create_project(session, body.name, types, created_by=user.id)
    return _one(session, p.id, user)


@router.post("/samples", response_model=ProjectOut, status_code=201)
def create_sample_project(session: SessionDep, user: UserDep, storage: StorageDep) -> ProjectOut:
    """A practice project with drawn pictures, for learning Katib."""
    project = samples.create_sample(session, storage, user.id)
    return _one(session, project.id, user)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, session: SessionDep, user: UserDep) -> ProjectOut:
    need(session, user, project_id, "view")
    return _one(session, project_id, user)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def rename_project(
    project_id: uuid.UUID, body: ProjectPatch, session: SessionDep, user: UserDep
) -> ProjectOut:
    need(session, user, project_id, "manage")
    if body.name is not None:
        projects.rename_project(session, project_id, body.name)
    if body.review_enabled is not None:
        tasks.set_review(session, project_id, body.review_enabled)
    return _one(session, project_id, user)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: uuid.UUID, session: SessionDep, user: UserDep) -> Response:
    need(session, user, project_id, "owner")
    projects.delete_project(session, project_id)
    return Response(status_code=204)
