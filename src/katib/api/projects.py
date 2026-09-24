"""Project routes."""

import uuid

from fastapi import APIRouter, Response
from sqlalchemy.orm import Session

from katib.api.deps import SessionDep
from katib.api.schemas import ProjectIn, ProjectOut, ProjectPatch
from katib.services import projects
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
def list_projects(session: SessionDep, q: str | None = None) -> list[ProjectOut]:
    return [_out(s) for s in projects.list_projects(session, q)]


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, session: SessionDep) -> ProjectOut:
    p = projects.create_project(session, body.name, list(body.annotation_types or []) or None)
    return _one(session, p.id)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, session: SessionDep) -> ProjectOut:
    return _one(session, project_id)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def rename_project(project_id: uuid.UUID, body: ProjectPatch, session: SessionDep) -> ProjectOut:
    projects.rename_project(session, project_id, body.name)
    return _one(session, project_id)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: uuid.UUID, session: SessionDep) -> Response:
    projects.delete_project(session, project_id)
    return Response(status_code=204)
