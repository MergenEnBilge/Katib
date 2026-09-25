"""Request dependencies: a transaction-scoped session, the signed-in user and shared services."""

import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session
from starlette.requests import HTTPConnection

from katib.api.hub import Hub
from katib.auth.ratelimit import LoginLimiter
from katib.config import Settings
from katib.db.models import User
from katib.jobs.runner import JobRunner
from katib.services import access, auth
from katib.services.access import Capability
from katib.services.errors import Unauthorized
from katib.services.images import StorageContext

SESSION_COOKIE = "katib_session"


def get_session(request: Request) -> Iterator[Session]:
    """One transaction per request: commit on success, roll back on any error.

    Used with scope="function" so the commit happens before the response is sent. With the
    default request scope, a fast client can ask for the new row before it is committed.
    """
    session: Session = request.app.state.session_factory()
    try:
        yield session
        session.commit()
        hub: Hub = request.app.state.hub
        for project_id, message in session.info.pop("events", []):
            hub.publish(project_id, message)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_session, scope="function")]


def _bearer(request: HTTPConnection) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None


def find_user(request: HTTPConnection, session: Session) -> User | None:
    """The person making the request, or None when nobody is signed in."""
    settings: Settings = request.app.state.settings
    if settings.auth.mode == "none":
        return auth.local_user(session)
    token = _bearer(request)
    if token:
        return auth.user_for_api_token(session, token)
    cookie = request.cookies.get(SESSION_COOKIE)
    return auth.user_for_session(session, cookie) if cookie else None


def client_address(request: HTTPConnection) -> str:
    """Who is asking. Behind a trusted proxy that is the last address it recorded."""
    settings: Settings = request.app.state.settings
    if settings.server.behind_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        last = forwarded.split(",")[-1].strip()
        if last:
            return last
    return request.client.host if request.client else "?"


def is_https(request: HTTPConnection) -> bool:
    """Whether the visitor used HTTPS, even when a proxy handled it and passed on plain HTTP."""
    settings: Settings = request.app.state.settings
    if settings.server.behind_proxy:
        return request.headers.get("x-forwarded-proto", "").split(",")[-1].strip() == "https"
    return request.url.scheme in ("https", "wss")


def get_current_user(request: Request, session: SessionDep) -> User:
    user = find_user(request, session)
    if user is None:
        raise Unauthorized("Sign in to continue.")
    return user


UserDep = Annotated[User, Depends(get_current_user, scope="function")]


def may_browse_anywhere(request: Request, user: UserDep) -> bool:
    """Alone on your own computer you may look anywhere. On a shared server, only administrators."""
    settings: Settings = request.app.state.settings
    return settings.auth.mode == "none" or user.is_admin


AnywhereDep = Annotated[bool, Depends(may_browse_anywhere, scope="function")]


def get_storage(request: Request) -> StorageContext:
    ctx: StorageContext = request.app.state.storage
    return ctx


def get_runner(request: Request) -> JobRunner:
    runner: JobRunner = request.app.state.runner
    return runner


def get_limiter(request: Request) -> LoginLimiter:
    limiter: LoginLimiter = request.app.state.limiter
    return limiter


StorageDep = Annotated[StorageContext, Depends(get_storage)]
RunnerDep = Annotated[JobRunner, Depends(get_runner)]
LimiterDep = Annotated[LoginLimiter, Depends(get_limiter)]


def need(session: Session, user: User, project_id: uuid.UUID, capability: Capability) -> None:
    """Raise unless `user` has `capability` in the project."""
    access.require(session, user, project_id, capability)
