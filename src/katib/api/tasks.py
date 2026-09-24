"""Work queue routes: next image, assignment, locks, comments, activity and the inbox."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from katib.api.deps import SessionDep, UserDep, need
from katib.api.hub import emit
from katib.api.images import _out as image_out
from katib.api.schemas import ImageOut, LockOut
from katib.db.models import Comment, Image, Project, ProjectMember
from katib.services import access, discussion, tasks
from katib.services.errors import NotFound
from katib.services.images import ImageRow

router = APIRouter(tags=["work queue"])


class NextOut(BaseModel):
    image: ImageOut | None


class AssignIn(BaseModel):
    image_ids: Annotated[list[uuid.UUID], Field(min_length=1, max_length=5000)]
    assignee_id: uuid.UUID | None = None


class AssignOut(BaseModel):
    assigned: int


class CommentIn(BaseModel):
    body: str
    annotation_id: uuid.UUID | None = None
    x: float | None = None
    y: float | None = None


class CommentOut(BaseModel):
    id: uuid.UUID
    author: str
    author_id: uuid.UUID
    body: str
    annotation_id: uuid.UUID | None
    x: float | None
    y: float | None
    resolved: bool
    created_at: datetime


class ResolveIn(BaseModel):
    resolved: bool = True


class ActivityOut(BaseModel):
    id: uuid.UUID
    who: str
    verb: str
    payload: dict[str, object]
    created_at: datetime


class InboxItem(BaseModel):
    project_id: uuid.UUID
    project_name: str
    image_id: uuid.UUID
    filename: str
    status: str


class InboxOut(BaseModel):
    assigned: list[InboxItem]
    to_review: list[InboxItem]


def _lock_out(image: Image, name: str | None, me: uuid.UUID) -> LockOut:
    assert image.locked_by is not None and image.locked_until is not None
    return LockOut(
        user_id=image.locked_by, name=name, until=image.locked_until, mine=image.locked_by == me
    )


def _lock_event(image: Image, name: str | None) -> dict[str, object]:
    return {
        "type": "image.locked",
        "image_id": str(image.id),
        "user_id": str(image.locked_by),
        "name": name,
    }


def _comment(row: discussion.CommentRow) -> CommentOut:
    c = row.comment
    return CommentOut(
        id=c.id,
        author=row.author,
        author_id=c.author_id,
        body=c.body,
        annotation_id=c.annotation_id,
        x=c.x,
        y=c.y,
        resolved=c.resolved_at is not None,
        created_at=c.created_at,
    )


@router.post("/projects/{project_id}/next", response_model=NextOut)
def next_image(project_id: uuid.UUID, session: SessionDep, user: UserDep) -> NextOut:
    need(session, user, project_id, "annotate")
    image = tasks.next_image(session, user, project_id)
    return NextOut(image=image_out(session, ImageRow(image, 0), user) if image else None)


@router.post("/projects/{project_id}/images:assign", response_model=AssignOut)
def assign(project_id: uuid.UUID, body: AssignIn, session: SessionDep, user: UserDep) -> AssignOut:
    need(session, user, project_id, "manage")
    count = tasks.assign(session, project_id, body.image_ids, body.assignee_id)
    discussion.log(
        session,
        project_id,
        user,
        "assigned",
        {"count": count, "assignee_id": str(body.assignee_id) if body.assignee_id else None},
    )
    return AssignOut(assigned=count)


@router.post("/images/{image_id}/lock", response_model=LockOut)
def lock(image_id: uuid.UUID, session: SessionDep, user: UserDep) -> LockOut:
    need(session, user, access.project_of_image(session, image_id), "annotate")
    image = tasks.lock_image(session, user, image_id)
    emit(session.info, image.project_id, _lock_event(image, user.name))
    return _lock_out(image, user.name, user.id)


@router.delete("/images/{image_id}/lock", status_code=204)
def unlock(image_id: uuid.UUID, session: SessionDep, user: UserDep) -> Response:
    need(session, user, access.project_of_image(session, image_id), "annotate")
    tasks.unlock_image(session, user, image_id)
    emit(
        session.info,
        access.project_of_image(session, image_id),
        {"type": "image.unlocked", "image_id": str(image_id)},
    )
    return Response(status_code=204)


@router.post("/images/{image_id}/lock:take-over", response_model=LockOut)
def take_over(image_id: uuid.UUID, session: SessionDep, user: UserDep) -> LockOut:
    need(session, user, access.project_of_image(session, image_id), "manage")
    image = tasks.take_over(session, image_id, user)
    emit(session.info, image.project_id, _lock_event(image, user.name))
    return _lock_out(image, user.name, user.id)


@router.get("/images/{image_id}/comments", response_model=list[CommentOut])
def list_comments(image_id: uuid.UUID, session: SessionDep, user: UserDep) -> list[CommentOut]:
    need(session, user, access.project_of_image(session, image_id), "view")
    return [_comment(r) for r in discussion.list_comments(session, image_id)]


@router.post("/images/{image_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(
    image_id: uuid.UUID, body: CommentIn, session: SessionDep, user: UserDep
) -> CommentOut:
    need(session, user, access.project_of_image(session, image_id), "annotate")
    comment = discussion.add_comment(
        session, user, image_id, body.body, body.annotation_id, body.x, body.y
    )
    return _comment(discussion.CommentRow(comment, user.name))


@router.post("/comments/{comment_id}:resolve", response_model=CommentOut)
def resolve_comment(
    comment_id: uuid.UUID, body: ResolveIn, session: SessionDep, user: UserDep
) -> CommentOut:
    existing = session.get(Comment, comment_id)
    if existing is None:
        raise NotFound("That comment does not exist.")
    need(session, user, access.project_of_image(session, existing.image_id), "annotate")
    comment = discussion.set_resolved(session, comment_id, body.resolved)
    rows = discussion.list_comments(session, comment.image_id)
    author = next(r.author for r in rows if r.comment.id == comment.id)
    return _comment(discussion.CommentRow(comment, author))


@router.get("/projects/{project_id}/activity", response_model=list[ActivityOut])
def activity(project_id: uuid.UUID, session: SessionDep, user: UserDep) -> list[ActivityOut]:
    need(session, user, project_id, "view")
    return [
        ActivityOut(id=a.id, who=name, verb=a.verb, payload=a.payload, created_at=a.created_at)
        for a, name in discussion.recent(session, project_id)
    ]


@router.get("/inbox", response_model=InboxOut)
def inbox(session: SessionDep, user: UserDep) -> InboxOut:
    """My unfinished images, and images waiting for my review, across projects."""
    mine = session.execute(
        select(Image, Project.name)
        .join(Project, Project.id == Image.project_id)
        .where(
            Image.assignee_id == user.id,
            Image.status.in_(("in_progress", "rejected")),
            Project.archived_at.is_(None),
        )
        .order_by(Project.name, Image.position)
        .limit(200)
    ).all()
    reviewer_of = select(ProjectMember.project_id).where(
        ProjectMember.user_id == user.id, ProjectMember.role.in_(("reviewer", "manager", "owner"))
    )
    stmt = (
        select(Image, Project.name)
        .join(Project, Project.id == Image.project_id)
        .where(Image.status == "done", Project.archived_at.is_(None))
        .order_by(Project.name, Image.position)
        .limit(200)
    )
    if not user.is_admin:
        stmt = stmt.where(Image.project_id.in_(reviewer_of))
    review = [(i, n) for i, n in session.execute(stmt).all()]
    review = [
        (i, n)
        for i, n in review
        if (p := session.get(Project, i.project_id)) is not None
        and p.settings.get("review_enabled")
    ]

    def item(i: Image, name: str) -> InboxItem:
        return InboxItem(
            project_id=i.project_id,
            project_name=name,
            image_id=i.id,
            filename=i.filename,
            status=i.status,
        )

    return InboxOut(
        assigned=[item(i, n) for i, n in mine], to_review=[item(i, n) for i, n in review]
    )
