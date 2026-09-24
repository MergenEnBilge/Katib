"""Comments on images and the activity feed."""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from katib.db.base import utcnow
from katib.db.models import Activity, Annotation, Comment, Image, User
from katib.services.errors import InvalidInput, NotFound

MAX_BODY = 2000


@dataclass(frozen=True)
class CommentRow:
    comment: Comment
    author: str


def log(
    session: Session,
    project_id: uuid.UUID,
    user: User | None,
    verb: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Record something worth showing in Recent activity. Not the same as the operations log."""
    session.add(
        Activity(
            project_id=project_id,
            user_id=user.id if user else None,
            verb=verb,
            payload=payload or {},
        )
    )


def recent(session: Session, project_id: uuid.UUID, limit: int = 30) -> list[tuple[Activity, str]]:
    rows = session.execute(
        select(Activity, User.name)
        .outerjoin(User, User.id == Activity.user_id)
        .where(Activity.project_id == project_id)
        .order_by(Activity.created_at.desc(), Activity.id.desc())
        .limit(max(1, min(limit, 100)))
    ).all()
    return [(a, name or "Someone") for a, name in rows]


def add_comment(
    session: Session,
    user: User,
    image_id: uuid.UUID,
    body: str,
    annotation_id: uuid.UUID | None = None,
    x: float | None = None,
    y: float | None = None,
) -> Comment:
    body = body.strip()
    if not body:
        raise InvalidInput("Write a comment first.")
    if len(body) > MAX_BODY:
        raise InvalidInput(f"Comments can be up to {MAX_BODY} characters.")
    image = session.get(Image, image_id)
    if image is None:
        raise NotFound("That image does not exist.")
    if annotation_id is not None:
        ann = session.get(Annotation, annotation_id)
        if ann is None or ann.image_id != image_id:
            raise InvalidInput("That shape is not on this image.")
    for value in (x, y):
        if value is not None and not 0.0 <= value <= 1.0:
            raise InvalidInput("A comment position must be inside the image.")
    comment = Comment(
        image_id=image_id, annotation_id=annotation_id, x=x, y=y, author_id=user.id, body=body
    )
    session.add(comment)
    session.flush()
    log(session, image.project_id, user, "commented", {"image_id": str(image_id)})
    return comment


def list_comments(session: Session, image_id: uuid.UUID) -> list[CommentRow]:
    rows = session.execute(
        select(Comment, User.name)
        .join(User, User.id == Comment.author_id)
        .where(Comment.image_id == image_id)
        .order_by(Comment.created_at)
    ).all()
    return [CommentRow(c, name) for c, name in rows]


def set_resolved(session: Session, comment_id: uuid.UUID, resolved: bool) -> Comment:
    comment = session.get(Comment, comment_id)
    if comment is None:
        raise NotFound("That comment does not exist.")
    comment.resolved_at = utcnow() if resolved else None
    session.flush()
    return comment
