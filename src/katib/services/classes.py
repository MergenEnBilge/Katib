"""Classes: create, rename, recolor, reorder, and lookup by name or alias.

Annotations point at `class_id`, so renaming never touches annotation rows. A rename keeps the
old name as an alias so older files still resolve on import.
"""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from katib.core.palette import next_color
from katib.db.models import Annotation, Class, ClassAlias
from katib.services.errors import ClassNameTaken, InvalidInput, NotFound

MAX_NAME = 200
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class ClassWithCount:
    cls: Class
    annotation_count: int


def _clean_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise InvalidInput("Give the class a name.")
    if len(name) > MAX_NAME:
        raise InvalidInput(f"Class names can be up to {MAX_NAME} characters.")
    return name


def _check_color(color: str) -> str:
    if not _HEX.match(color):
        raise InvalidInput("Colors look like #4C8DF6.")
    return color.upper()


def _taken(
    session: Session, project_id: uuid.UUID, name: str, exclude: uuid.UUID | None = None
) -> bool:
    stmt = select(Class.id).where(
        Class.project_id == project_id, func.lower(Class.name) == name.lower()
    )
    if exclude is not None:
        stmt = stmt.where(Class.id != exclude)
    return session.scalar(stmt.limit(1)) is not None


def get_class(session: Session, class_id: uuid.UUID) -> Class:
    cls = session.get(Class, class_id)
    if cls is None:
        raise NotFound("That class does not exist.")
    return cls


def create_class(
    session: Session, project_id: uuid.UUID, name: str, color: str | None = None
) -> Class:
    name = _clean_name(name)
    if _taken(session, project_id, name):
        raise ClassNameTaken(f"A class named “{name}” already exists.", name=name)
    existing = list(
        session.execute(
            select(Class.color, Class.position).where(Class.project_id == project_id)
        ).all()
    )
    used = [c for c, _ in existing]
    position = max((p for _, p in existing), default=-1) + 1
    chosen = _check_color(color) if color else next_color(used)
    cls = Class(project_id=project_id, name=name, color=chosen, position=position)
    session.add(cls)
    # A new class takes over its name from any alias so lookups stay unambiguous.
    session.execute(
        delete(ClassAlias).where(
            ClassAlias.project_id == project_id, ClassAlias.alias == name.lower()
        )
    )
    session.flush()
    return cls


def list_classes(session: Session, project_id: uuid.UUID) -> list[ClassWithCount]:
    stmt = (
        select(Class, func.count(Annotation.id))
        .outerjoin(Annotation, Annotation.class_id == Class.id)
        .where(Class.project_id == project_id)
        .group_by(Class.id)
        .order_by(Class.position)
    )
    return [ClassWithCount(c, n) for c, n in session.execute(stmt).all()]


def rename_class(session: Session, class_id: uuid.UUID, name: str) -> Class:
    cls = get_class(session, class_id)
    name = _clean_name(name)
    if name == cls.name:
        return cls
    if _taken(session, cls.project_id, name, exclude=cls.id):
        raise ClassNameTaken(f"A class named “{name}” already exists.", name=name)
    old = cls.name.lower()
    cls.name = name
    session.execute(
        delete(ClassAlias).where(
            ClassAlias.project_id == cls.project_id, ClassAlias.alias == name.lower()
        )
    )
    if old != name.lower() and session.get(ClassAlias, (cls.project_id, old)) is None:
        session.add(ClassAlias(project_id=cls.project_id, alias=old, class_id=cls.id))
    session.flush()
    return cls


def recolor_class(session: Session, class_id: uuid.UUID, color: str) -> Class:
    cls = get_class(session, class_id)
    cls.color = _check_color(color)
    session.flush()
    return cls


def reorder_classes(session: Session, project_id: uuid.UUID, ordered_ids: list[uuid.UUID]) -> None:
    """Set positions to match `ordered_ids`, which must list every class in the project once."""
    current = set(session.scalars(select(Class.id).where(Class.project_id == project_id)))
    if set(ordered_ids) != current or len(ordered_ids) != len(current):
        raise InvalidInput("The new order must list every class exactly once.")
    for position, class_id in enumerate(ordered_ids):
        session.execute(update(Class).where(Class.id == class_id).values(position=position))
    session.flush()


def resolve_class(session: Session, project_id: uuid.UUID, name: str) -> Class | None:
    """Find a class by current name or alias, ignoring case. Used by imports."""
    lowered = name.strip().lower()
    cls = session.scalar(
        select(Class).where(Class.project_id == project_id, func.lower(Class.name) == lowered)
    )
    if cls is not None:
        return cls
    alias = session.get(ClassAlias, (project_id, lowered))
    return session.get(Class, alias.class_id) if alias else None
