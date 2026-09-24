"""Who may do what. Roles are per project. Administrators count as owners everywhere.

view      read a project
annotate  create and edit shapes, mark images done
review    approve or reject, comment
manage    import, classes, assignment, export
owner     delete the project, manage members
"""

import uuid
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from katib.db.models import Annotation, Class, Image, Job, Operation, ProjectMember, User
from katib.services.errors import Forbidden, InvalidInput, NotFound

Capability = Literal["view", "annotate", "review", "manage", "owner"]

ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    "owner": frozenset({"view", "annotate", "review", "manage", "owner"}),
    "manager": frozenset({"view", "annotate", "review", "manage"}),
    "reviewer": frozenset({"view", "annotate", "review"}),
    "annotator": frozenset({"view", "annotate"}),
    "viewer": frozenset({"view"}),
}
ROLES = tuple(ROLE_CAPABILITIES)


def role_of(session: Session, user: User, project_id: uuid.UUID) -> str | None:
    if user.is_admin:
        return "owner"
    member = session.get(ProjectMember, (project_id, user.id))
    return member.role if member else None


def require(session: Session, user: User, project_id: uuid.UUID, capability: Capability) -> str:
    """Return the caller's role or raise. Non-members get NotFound so projects do not leak."""
    role = role_of(session, user, project_id)
    if role is None:
        raise NotFound("That project does not exist.")
    if capability not in ROLE_CAPABILITIES[role]:
        raise Forbidden("You do not have permission to do that in this project.")
    return role


def visible_project_ids(session: Session, user: User) -> set[uuid.UUID] | None:
    """Ids of projects the user can see, or None when they can see all of them."""
    if user.is_admin:
        return None
    rows = session.scalars(select(ProjectMember.project_id).where(ProjectMember.user_id == user.id))
    return set(rows)


def add_member(session: Session, project_id: uuid.UUID, user_id: uuid.UUID, role: str) -> None:
    if role not in ROLES:
        raise InvalidInput("Unknown role.")
    if session.get(User, user_id) is None:
        raise NotFound("That person does not exist.")
    member = session.get(ProjectMember, (project_id, user_id))
    if member is None:
        session.add(ProjectMember(project_id=project_id, user_id=user_id, role=role))
    else:
        member.role = role
    session.flush()


def remove_member(session: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
    member = session.get(ProjectMember, (project_id, user_id))
    if member is None:
        raise NotFound("That person is not in this project.")
    if member.role == "owner":
        owners = session.scalars(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id, ProjectMember.role == "owner"
            )
        ).all()
        if len(owners) <= 1:
            raise InvalidInput("A project needs at least one owner.")
    session.delete(member)
    session.flush()


def list_members(session: Session, project_id: uuid.UUID) -> list[tuple[User, str]]:
    rows = session.execute(
        select(User, ProjectMember.role)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .where(ProjectMember.project_id == project_id)
        .order_by(User.name)
    ).all()
    return [(u, r) for u, r in rows]


def project_of_image(session: Session, image_id: uuid.UUID) -> uuid.UUID:
    image = session.get(Image, image_id)
    if image is None:
        raise NotFound("That image does not exist.")
    return image.project_id


def project_of_class(session: Session, class_id: uuid.UUID) -> uuid.UUID:
    cls = session.get(Class, class_id)
    if cls is None:
        raise NotFound("That class does not exist.")
    return cls.project_id


def project_of_annotation(session: Session, annotation_id: uuid.UUID) -> uuid.UUID:
    ann = session.get(Annotation, annotation_id)
    if ann is None:
        raise NotFound("That shape does not exist.")
    return project_of_image(session, ann.image_id)


def project_of_operation(session: Session, operation_id: uuid.UUID) -> uuid.UUID:
    op = session.get(Operation, operation_id)
    if op is None:
        raise NotFound("That operation does not exist.")
    return op.project_id


def project_of_job(session: Session, job_id: uuid.UUID) -> uuid.UUID | None:
    job = session.get(Job, job_id)
    if job is None:
        raise NotFound("That job does not exist.")
    return job.project_id
