"""Project routes."""

import uuid

from fastapi import APIRouter, Response
from sqlalchemy.orm import Session

from katib.api.deps import SessionDep, UserDep, need
from katib.api.schemas import ProjectIn, ProjectOut, ProjectPatch
from katib.services import access, projects
from katib.services.errors import NotFound
from katib.services.projects import ProjectSummary

router = APIRouter(tags=["projects"])


def _out(s: ProjectSummary) -> ProjectOut:
    p = s.project
    return ProjectOut(
        id=p.id,
        name=p.name,
        slug=p.slug,
        annotation_types=list(p.settings.get("annotation_types", [])),
        image_count=s.image_count,
        done_count=s.done_count,
        created_at=p.created_at,
        last_edited=s.last_edited,
    )


def _one(session: Session, project_id: uuid.UUID) -> ProjectOut:
    for s in projects.list_projects(session):
        if s.project.id == project_id:
            return _out(s)
    raise NotFound("That project does not exist.")


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(session: SessionDep, user: UserDep, q: str | None = None) -> list[ProjectOut]:
    visible = access.visible_project_ids(session, user)
    return [_out(s) for s in projects.list_projects(session, q, visible)]


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, session: SessionDep, user: UserDep) -> ProjectOut:
    types: list[str] | None = [str(t) for t in body.annotation_types or []] or None
    p = projects.create_project(session, body.name, types, created_by=user.id)
    return _one(session, p.id)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, session: SessionDep, user: UserDep) -> ProjectOut:
    need(session, user, project_id, "view")
    return _one(session, project_id)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def rename_project(
    project_id: uuid.UUID, body: ProjectPatch, session: SessionDep, user: UserDep
) -> ProjectOut:
    need(session, user, project_id, "manage")
    projects.rename_project(session, project_id, body.name)
    return _one(session, project_id)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: uuid.UUID, session: SessionDep, user: UserDep) -> Response:
    need(session, user, project_id, "owner")
    projects.delete_project(session, project_id)
    return Response(status_code=204)
