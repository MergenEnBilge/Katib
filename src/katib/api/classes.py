"""Class routes."""

import uuid

from fastapi import APIRouter, Response
from sqlalchemy.orm import Session

from katib.api.deps import SessionDep, UserDep, need
from katib.api.hub import emit
from katib.api.schemas import AttrDef, ClassIn, ClassOut, ClassPatch, ReorderIn, Skeleton
from katib.services import access, classes, projects
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
        attr_schema=[AttrDef.model_validate(a) for a in c.cls.attr_schema],
        skeleton=Skeleton.model_validate(c.cls.skeleton) if c.cls.skeleton else None,
    )


def _one(session: Session, project_id: uuid.UUID, class_id: uuid.UUID) -> ClassOut:
    return next(_out(c) for c in classes.list_classes(session, project_id) if c.cls.id == class_id)


@router.get("/projects/{project_id}/classes", response_model=list[ClassOut])
def list_classes(project_id: uuid.UUID, session: SessionDep, user: UserDep) -> list[ClassOut]:
    need(session, user, project_id, "view")
    projects.get_project(session, project_id)
    return [_out(c) for c in classes.list_classes(session, project_id)]


@router.post("/projects/{project_id}/classes", response_model=ClassOut, status_code=201)
def create_class(
    project_id: uuid.UUID, body: ClassIn, session: SessionDep, user: UserDep
) -> ClassOut:
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    cls = classes.create_class(session, project_id, body.name, body.color)
    emit(session.info, project_id, {"type": "class.changed"})
    return _one(session, project_id, cls.id)


@router.patch("/classes/{class_id}", response_model=ClassOut)
def update_class(
    class_id: uuid.UUID, body: ClassPatch, session: SessionDep, user: UserDep
) -> ClassOut:
    need(session, user, access.project_of_class(session, class_id), "manage")
    cls = classes.get_class(session, class_id)
    if body.name is not None:
        classes.rename_class(session, class_id, body.name)
    if body.color is not None:
        classes.recolor_class(session, class_id, body.color)
    if body.attr_schema is not None:
        classes.set_attr_schema(
            session, class_id, [a.model_dump(exclude_none=True) for a in body.attr_schema]
        )
    if body.skeleton is not None:
        classes.set_skeleton(session, class_id, body.skeleton.names, body.skeleton.edges)
    emit(session.info, cls.project_id, {"type": "class.changed"})
    return _one(session, cls.project_id, class_id)


@router.post("/projects/{project_id}/classes:reorder", status_code=204)
def reorder_classes(
    project_id: uuid.UUID, body: ReorderIn, session: SessionDep, user: UserDep
) -> Response:
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    classes.reorder_classes(session, project_id, body.class_ids)
    emit(session.info, project_id, {"type": "class.changed"})
    return Response(status_code=204)
