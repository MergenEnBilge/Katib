"""Who may do what. Roles are per project. Administrators count as owners everywhere.

view      read a project
annotate  create and edit shapes, mark images done
review    approve or reject, comment
manage    import, classes, assignment, export, and bring in annotators, reviewers and viewers
owner     delete the project, manage every member including other owners and managers
"""

import uuid
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from katib.db.models import Annotation, Class, Image, Job, Operation, Project, ProjectMember, User
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

#: The roles a manager may hand out, change between, or take away.
MANAGER_ASSIGNABLE = frozenset({"annotator", "reviewer", "viewer"})


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


def can_assign(actor_role: str, current_role: str | None, new_role: str | None) -> bool:
    """Whether someone with `actor_role` may move a person from `current_role` to `new_role`.

    None stands for "not in the project", before an addition or after a removal.
    """
    if actor_role == "owner":
        return True
    if actor_role == "manager":
        return all(r is None or r in MANAGER_ASSIGNABLE for r in (current_role, new_role))
    return False


def require_assign(
    session: Session, actor: User, project_id: uuid.UUID, user_id: uuid.UUID, new_role: str | None
) -> None:
    """Raise unless `actor` may give `user_id` the role `new_role` here (None removes them)."""
    actor_role = require(session, actor, project_id, "manage")
    member = session.get(ProjectMember, (project_id, user_id))
    if not can_assign(actor_role, member.role if member else None, new_role):
        raise Forbidden(
            "Managers can add, change and remove annotators, reviewers and viewers. "
            "Ask an owner for anything else."
        )


def _owner_count(session: Session, project_id: uuid.UUID) -> int:
    owners = session.scalars(
        select(ProjectMember.user_id).where(
            ProjectMember.project_id == project_id, ProjectMember.role == "owner"
        )
    ).all()
    return len(owners)


def add_member(session: Session, project_id: uuid.UUID, user_id: uuid.UUID, role: str) -> None:
    if role not in ROLES:
        raise InvalidInput("Unknown role.")
    if session.get(User, user_id) is None:
        raise NotFound("That person does not exist.")
    member = session.get(ProjectMember, (project_id, user_id))
    if member is None:
        session.add(ProjectMember(project_id=project_id, user_id=user_id, role=role))
    else:
        if member.role == "owner" and role != "owner" and _owner_count(session, project_id) <= 1:
            raise InvalidInput("A project needs at least one owner. Make someone else owner first.")
        member.role = role
    session.flush()


def remove_member(session: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
    member = session.get(ProjectMember, (project_id, user_id))
    if member is None:
        raise NotFound("That person is not in this project.")
    if member.role == "owner" and _owner_count(session, project_id) <= 1:
        raise InvalidInput("A project needs at least one owner.")
    session.delete(member)
    session.flush()


def addable_people(
    session: Session,
    project_id: uuid.UUID,
    query: str = "",
    limit: int = 20,
    *,
    exact_email: bool = False,
) -> list[User]:
    """Active accounts not yet in the project, matching `query` by name or email.

    With `exact_email` only an account whose email is exactly `query` is returned. That is what
    everyone but administrators gets: anyone may make a project and so become its owner, and a
    partial search would let them list every account on the server, one letter at a time.
    """
    members = select(ProjectMember.user_id).where(ProjectMember.project_id == project_id)
    stmt = select(User).where(
        User.id.not_in(members),
        User.disabled_at.is_(None),
        # The implicit single-user account has no password and is nobody to add.
        User.password_hash.is_not(None),
    )
    text = query.strip().lower()
    if exact_email:
        if not text:
            return []
        stmt = stmt.where(User.email == text)
    elif text:
        like = f"%{text}%"
        stmt = stmt.where(User.name.ilike(like) | User.email.ilike(like))
    return list(session.scalars(stmt.order_by(User.name).limit(limit)))


def projects_of(session: Session, user_id: uuid.UUID) -> list[tuple[Project, str]]:
    """The projects a person is a member of, and their role in each."""
    rows = session.execute(
        select(Project, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user_id)
        .order_by(Project.name)
    ).all()
    return [(p, r) for p, r in rows]


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
