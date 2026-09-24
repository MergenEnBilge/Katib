"""Class routes."""

import uuid

from fastapi import APIRouter, Response
from sqlalchemy.orm import Session

from katib.api.deps import SessionDep
from katib.api.schemas import ClassIn, ClassOut, ClassPatch, ReorderIn
from katib.services import classes, projects
from katib.services.classes import ClassWithCount

router = APIRouter(tags=["classes"])


def _out(c: ClassWithCount) -> ClassOut:
    return ClassOut(
        id=c.cls.id,
        project_id=c.cls.project_id,
        name=c.cls.name,
        color=c.cls.color,
        position=c.cls.position,
        annotation_count=c.annotation_count,
    )


def _one(session: Session, project_id: uuid.UUID, class_id: uuid.UUID) -> ClassOut:
    return next(_out(c) for c in classes.list_classes(session, project_id) if c.cls.id == class_id)


@router.get("/projects/{project_id}/classes", response_model=list[ClassOut])
def list_classes(project_id: uuid.UUID, session: SessionDep) -> list[ClassOut]:
    projects.get_project(session, project_id)
    return [_out(c) for c in classes.list_classes(session, project_id)]


@router.post("/projects/{project_id}/classes", response_model=ClassOut, status_code=201)
def create_class(project_id: uuid.UUID, body: ClassIn, session: SessionDep) -> ClassOut:
    projects.get_project(session, project_id)
    cls = classes.create_class(session, project_id, body.name, body.color)
    return _one(session, project_id, cls.id)


@router.patch("/classes/{class_id}", response_model=ClassOut)
def update_class(class_id: uuid.UUID, body: ClassPatch, session: SessionDep) -> ClassOut:
    cls = classes.get_class(session, class_id)
    if body.name is not None:
        classes.rename_class(session, class_id, body.name)
    if body.color is not None:
        classes.recolor_class(session, class_id, body.color)
    return _one(session, cls.project_id, class_id)


@router.post("/projects/{project_id}/classes:reorder", status_code=204)
def reorder_classes(project_id: uuid.UUID, body: ReorderIn, session: SessionDep) -> Response:
    projects.get_project(session, project_id)
    classes.reorder_classes(session, project_id, body.class_ids)
    return Response(status_code=204)
