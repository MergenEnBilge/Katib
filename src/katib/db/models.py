"""SQLAlchemy models. Tables and columns follow ARCHITECTURE.md section 6.

No business rules live here. Geometry is stored normalized (0 to 1) in JSON columns.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from katib.db.base import Base, UTCDateTime, utcnow
from katib.db.ids import new_id


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    disabled_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    settings: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20))


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (
        Index("ix_images_project_status", "project_id", "status"),
        Index("ix_images_project_position", "project_id", "position"),
        Index("ix_images_project_assignee", "project_id", "assignee_id"),
        Index("ix_images_project_split", "project_id", "split"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(1024))
    storage_key: Mapped[str] = mapped_column(String(2048))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    phash: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="todo")
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    locked_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime)
    position: Mapped[int] = mapped_column(Integer)
    #: "train", "val" or "test", or None while the image is not in a split.
    split: Mapped[str | None] = mapped_column(String(10))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class ProjectFolder(Base):
    """A folder on the Katib computer that a project reads its images from."""

    __tablename__ = "project_folders"
    __table_args__ = (UniqueConstraint("project_id", "path"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Class(Base):
    __tablename__ = "classes"
    __table_args__ = (
        Index("uq_classes_project_lower_name", "project_id", text("lower(name)"), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    color: Mapped[str] = mapped_column(String(9))
    position: Mapped[int] = mapped_column(Integer)
    attr_schema: Mapped[list[Any]] = mapped_column(default=list)
    # Landmark names and the lines between them, for classes drawn with the keypoints tool.
    skeleton: Mapped[dict[str, Any] | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ClassAlias(Base):
    __tablename__ = "class_aliases"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    alias: Mapped[str] = mapped_column(String(200), primary_key=True)
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"))


class Annotation(Base):
    __tablename__ = "annotations"
    __table_args__ = (
        Index("ix_annotations_image_id", "image_id"),
        Index("ix_annotations_class_id", "class_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)  # supplied by the client
    image_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"))
    class_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("classes.id"))
    type: Mapped[str] = mapped_column(String(20))
    geometry: Mapped[dict[str, Any]] = mapped_column(default=dict)
    attrs: Mapped[dict[str, Any]] = mapped_column(default=dict)
    source: Mapped[str] = mapped_column(String(10), default="manual")
    confidence: Mapped[float | None] = mapped_column(Float)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    image_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"))
    annotation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("annotations.id", ondelete="SET NULL")
    )
    x: Mapped[float | None] = mapped_column(Float)
    y: Mapped[float | None] = mapped_column(Float)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Operation(Base):
    __tablename__ = "operations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(Text)
    inverse_ref: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    reverted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Activity(Base):
    __tablename__ = "activity"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verb: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    params: Mapped[dict[str, Any]] = mapped_column(default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column()
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class AuthSession(Base):
    """A browser login. Only the hash of the cookie value is stored."""

    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Invite(Base):
    """A single-use link that lets one person create an account."""

    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(20), default="annotator")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


__all__ = [
    "Activity",
    "Annotation",
    "AuthSession",
    "ApiToken",
    "Class",
    "ClassAlias",
    "Comment",
    "Image",
    "Invite",
    "Job",
    "Operation",
    "Project",
    "ProjectMember",
    "User",
]
