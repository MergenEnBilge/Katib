"""The work queue: next image, assignment, soft locks and status changes with review.

Claims and locks use conditional UPDATE statements, so two people asking at the same moment
cannot both win, on SQLite and on Postgres alike (ARCHITECTURE.md section 9).
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from katib.db.base import utcnow
from katib.db.models import Image, Project, User
from katib.services import access
from katib.services.errors import Forbidden, InvalidInput, KatibError, NotFound

LOCK_SECONDS = 45
CLAIM_CANDIDATES = 10
CLAIM_ATTEMPTS = 5
_WORKING = ("todo", "in_progress", "rejected")


class ImageLocked(KatibError):
    code = "image_locked"
    status = 409


def _rows(result: object) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


def get_image(session: Session, image_id: uuid.UUID) -> Image:
    image = session.get(Image, image_id)
    if image is None:
        raise NotFound("That image does not exist.")
    return image


def next_image(session: Session, user: User, project_id: uuid.UUID) -> Image | None:
    """Give the caller an image to work on.

    Their own unfinished image comes first. Otherwise the next `todo` image that nobody has
    claimed is assigned to them and moved to `in_progress`.
    """
    now = utcnow()
    mine = session.scalar(
        select(Image)
        .where(
            Image.project_id == project_id,
            Image.assignee_id == user.id,
            Image.status.in_(("in_progress", "rejected")),
            or_(Image.locked_by.is_(None), Image.locked_by == user.id, Image.locked_until <= now),
        )
        .order_by(Image.position)
        .limit(1)
    )
    if mine is not None:
        return mine

    stmt = (
        select(Image.id)
        .where(
            Image.project_id == project_id,
            Image.status == "todo",
            or_(Image.assignee_id.is_(None), Image.assignee_id == user.id),
        )
        .order_by(Image.position)
        .limit(CLAIM_CANDIDATES)
    )
    if session.get_bind().dialect.name == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)
    # Other people may claim the candidates first, so look again a few times before giving up.
    for _attempt in range(CLAIM_ATTEMPTS):
        candidates = session.scalars(stmt).all()
        if not candidates:
            return None
        for image_id in candidates:
            won = session.execute(
                update(Image)
                .where(
                    Image.id == image_id,
                    Image.status == "todo",
                    or_(Image.assignee_id.is_(None), Image.assignee_id == user.id),
                )
                .values(assignee_id=user.id, status="in_progress", version=Image.version + 1)
            )
            if _rows(won) == 1:
                session.flush()
                session.expire_all()
                return get_image(session, image_id)
    return None


def assign(
    session: Session,
    project_id: uuid.UUID,
    image_ids: list[uuid.UUID],
    assignee_id: uuid.UUID | None,
) -> int:
    """Assign images to a member, or clear the assignment with None. Returns how many changed."""
    if assignee_id is not None:
        person = session.get(User, assignee_id)
        if person is None or access.role_of(session, person, project_id) is None:
            raise InvalidInput("That person is not in this project.")
    if not image_ids:
        raise InvalidInput("Choose at least one image.")
    result = session.execute(
        update(Image)
        .where(Image.project_id == project_id, Image.id.in_(image_ids))
        .values(assignee_id=assignee_id, version=Image.version + 1)
    )
    return _rows(result)


def _holder(session: Session, image: Image) -> dict[str, object]:
    holder = session.get(User, image.locked_by) if image.locked_by else None
    return {
        "user_id": str(image.locked_by) if image.locked_by else None,
        "name": holder.name if holder else None,
        "until": image.locked_until.isoformat() if image.locked_until else None,
    }


def lock_image(
    session: Session, user: User, image_id: uuid.UUID, now: datetime | None = None
) -> Image:
    """Take or renew the 45 second edit lock. Raises ImageLocked when someone else holds it."""
    now = now or utcnow()
    until = now + timedelta(seconds=LOCK_SECONDS)
    won = session.execute(
        update(Image)
        .where(
            Image.id == image_id,
            or_(
                Image.locked_by.is_(None),
                Image.locked_by == user.id,
                Image.locked_until.is_(None),
                Image.locked_until <= now,
            ),
        )
        .values(locked_by=user.id, locked_until=until)
    )
    session.expire_all()
    image = get_image(session, image_id)
    if _rows(won) == 0:
        holder = _holder(session, image)
        raise ImageLocked(f"{holder['name'] or 'Someone'} is editing this image.", **holder)
    return image


def unlock_image(session: Session, user: User, image_id: uuid.UUID) -> None:
    session.execute(
        update(Image)
        .where(Image.id == image_id, Image.locked_by == user.id)
        .values(locked_by=None, locked_until=None)
    )


def take_over(session: Session, image_id: uuid.UUID, user: User) -> Image:
    """A manager takes the lock from someone else."""
    session.execute(
        update(Image)
        .where(Image.id == image_id)
        .values(locked_by=user.id, locked_until=utcnow() + timedelta(seconds=LOCK_SECONDS))
    )
    session.expire_all()
    return get_image(session, image_id)


def lock_state(
    session: Session, image: Image, now: datetime | None = None
) -> dict[str, object] | None:
    now = now or utcnow()
    if image.locked_by is None or image.locked_until is None or image.locked_until <= now:
        return None
    return _holder(session, image)


def transition(session: Session, user: User, image_id: uuid.UUID, new_status: str) -> Image:
    """Move an image through todo, in progress, done, approved or rejected.

    Annotators finish and reopen their own work. Approving and rejecting needs the review
    capability and review switched on for the project.
    """
    image = get_image(session, image_id)
    role = access.require(session, user, image.project_id, "annotate")
    current = image.status
    if new_status == current:
        return image

    if new_status in ("approved", "rejected"):
        access.require(session, user, image.project_id, "review")
        project = session.get(Project, image.project_id)
        if not (project and project.settings.get("review_enabled")):
            raise InvalidInput(
                "Review is off for this project. Turn it on in the project settings."
            )
        if current not in ("done", "approved", "rejected"):
            raise InvalidInput("Only images marked as done can be reviewed.")
    elif new_status == "done":
        if current not in _WORKING:
            raise InvalidInput("This image is already finished.")
    elif new_status in ("in_progress", "todo"):
        if current == "approved" and role not in ("owner", "manager", "reviewer"):
            raise Forbidden("Approved images can only be reopened by a reviewer.")
    else:
        raise InvalidInput("Unknown image status.")

    image.status = new_status
    if new_status == "done" and image.assignee_id is None:
        image.assignee_id = user.id
    if new_status in ("approved", "rejected"):
        image.reviewer_id = user.id
    image.version += 1
    session.flush()
    return image


def set_review(session: Session, project_id: uuid.UUID, enabled: bool) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise NotFound("That project does not exist.")
    project.settings = {**project.settings, "review_enabled": enabled}
    session.flush()
    return project
