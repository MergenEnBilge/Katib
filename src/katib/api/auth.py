"""Sign in, sign out, first-run setup, invites, API tokens, people and project members."""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from katib.api.deps import (
    SESSION_COOKIE,
    LimiterDep,
    SessionDep,
    UserDep,
    client_address,
    find_user,
    is_https,
    need,
)
from katib.config import Settings
from katib.db.models import User
from katib.services import access, auth
from katib.services.errors import Forbidden, InvalidInput, TooManyAttempts, Unauthorized

router = APIRouter(tags=["auth"])


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    is_admin: bool
    disabled: bool = False


class StatusOut(BaseModel):
    mode: Literal["none", "local"]
    needs_setup: bool
    user: UserOut | None


class SetupIn(BaseModel):
    email: str
    name: str = ""
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


class InviteIn(BaseModel):
    project_id: uuid.UUID | None = None
    role: Literal["manager", "annotator", "reviewer", "viewer"] = "annotator"


class InviteOut(BaseModel):
    token: str
    path: str


class InviteInfoOut(BaseModel):
    project: str | None
    role: str


class AcceptIn(BaseModel):
    token: str
    email: str
    name: str = ""
    password: str


class TokenIn(BaseModel):
    name: str


class TokenOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    last_used_at: datetime | None
    token: str | None = None


class MemberOut(BaseModel):
    user: UserOut
    role: str


class MemberIn(BaseModel):
    role: Literal["owner", "manager", "annotator", "reviewer", "viewer"]


def _user(u: User) -> UserOut:
    return UserOut(
        id=u.id, email=u.email, name=u.name, is_admin=u.is_admin, disabled=u.disabled_at is not None
    )


def _set_cookie(request: Request, response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=auth.SESSION_DAYS * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=is_https(request),
        path="/",
    )


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


@router.get("/auth/status", response_model=StatusOut)
def status(request: Request, session: SessionDep) -> StatusOut:
    settings = _settings(request)
    user = find_user(request, session)
    return StatusOut(
        mode=settings.auth.mode,
        needs_setup=settings.auth.mode == "local" and not auth.has_users(session),
        user=_user(user) if user else None,
    )


@router.post("/auth/setup", response_model=UserOut, status_code=201)
def setup(body: SetupIn, request: Request, response: Response, session: SessionDep) -> UserOut:
    if _settings(request).auth.mode != "local":
        raise Forbidden('Accounts are off. Turn on auth.mode = "local" to create them.')
    user = auth.setup_first_admin(session, body.email, body.name, body.password)
    _, token = auth.login(session, body.email, body.password)
    _set_cookie(request, response, token)
    return _user(user)


@router.post("/auth/login", response_model=UserOut)
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    session: SessionDep,
    limiter: LimiterDep,
) -> UserOut:
    keys = [
        f"email:{body.email.strip().lower()}",
        f"ip:{client_address(request)}",
    ]
    wait = max(limiter.retry_after(k) for k in keys)
    if wait:
        raise TooManyAttempts(f"Too many attempts. Try again in {wait} seconds.", retry_after=wait)
    try:
        user, token = auth.login(session, body.email, body.password)
    except Unauthorized:
        for k in keys:
            limiter.fail(k)
        raise
    for k in keys:
        limiter.reset(k)
    _set_cookie(request, response, token)
    return _user(user)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, session: SessionDep) -> Response:
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie:
        auth.logout(session, cookie)
    done = Response(status_code=204)
    done.delete_cookie(SESSION_COOKIE, path="/")
    return done


@router.get("/auth/invites/{token}", response_model=InviteInfoOut)
def invite_info(token: str, session: SessionDep) -> InviteInfoOut:
    info = auth.invite_info(session, token)
    return InviteInfoOut(project=info["project"], role=str(info["role"]))


@router.post("/auth/accept", response_model=UserOut, status_code=201)
def accept(body: AcceptIn, request: Request, response: Response, session: SessionDep) -> UserOut:
    user = auth.accept_invite(session, body.token, body.email, body.name, body.password)
    _, token = auth.login(session, body.email, body.password)
    _set_cookie(request, response, token)
    return _user(user)


@router.post("/invites", response_model=InviteOut, status_code=201)
def create_invite(body: InviteIn, session: SessionDep, user: UserDep) -> InviteOut:
    if body.project_id is None:
        if not user.is_admin:
            raise Forbidden("Only administrators can invite people without a project.")
    else:
        need(session, user, body.project_id, "manage")
    token = auth.create_invite(session, user, body.project_id, body.role)
    return InviteOut(token=token, path=f"/invite/{token}")


@router.get("/auth/tokens", response_model=list[TokenOut])
def list_tokens(session: SessionDep, user: UserDep) -> list[TokenOut]:
    return [
        TokenOut(id=t.id, name=t.name, created_at=t.created_at, last_used_at=t.last_used_at)
        for t in auth.list_api_tokens(session, user)
    ]


@router.post("/auth/tokens", response_model=TokenOut, status_code=201)
def create_token(body: TokenIn, session: SessionDep, user: UserDep) -> TokenOut:
    row, token = auth.create_api_token(session, user, body.name)
    return TokenOut(
        id=row.id, name=row.name, created_at=row.created_at, last_used_at=None, token=token
    )


@router.delete("/auth/tokens/{token_id}", status_code=204)
def revoke_token(token_id: uuid.UUID, session: SessionDep, user: UserDep) -> Response:
    auth.revoke_api_token(session, user, token_id)
    return Response(status_code=204)


@router.get("/users", response_model=list[UserOut])
def list_users(session: SessionDep, user: UserDep) -> list[UserOut]:
    if not user.is_admin:
        raise Forbidden("Only administrators can see everyone.")
    return [_user(u) for u in auth.list_users(session)]


@router.post("/users/{user_id}:disable", response_model=UserOut)
def disable_user(user_id: uuid.UUID, session: SessionDep, user: UserDep) -> UserOut:
    if not user.is_admin:
        raise Forbidden("Only administrators can disable accounts.")
    return _user(auth.set_disabled(session, user_id, True, user))


@router.post("/users/{user_id}:enable", response_model=UserOut)
def enable_user(user_id: uuid.UUID, session: SessionDep, user: UserDep) -> UserOut:
    if not user.is_admin:
        raise Forbidden("Only administrators can enable accounts.")
    return _user(auth.set_disabled(session, user_id, False, user))


@router.get("/projects/{project_id}/members", response_model=list[MemberOut])
def members(project_id: uuid.UUID, session: SessionDep, user: UserDep) -> list[MemberOut]:
    need(session, user, project_id, "view")
    return [MemberOut(user=_user(u), role=r) for u, r in access.list_members(session, project_id)]


@router.put("/projects/{project_id}/members/{user_id}", response_model=list[MemberOut])
def set_member(
    project_id: uuid.UUID, user_id: uuid.UUID, body: MemberIn, session: SessionDep, user: UserDep
) -> list[MemberOut]:
    need(session, user, project_id, "owner")
    if user_id == user.id and body.role != "owner" and not user.is_admin:
        raise InvalidInput("You cannot remove your own ownership. Ask another owner.")
    access.add_member(session, project_id, user_id, body.role)
    return [MemberOut(user=_user(u), role=r) for u, r in access.list_members(session, project_id)]


@router.delete("/projects/{project_id}/members/{user_id}", response_model=list[MemberOut])
def remove_member(
    project_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep, user: UserDep
) -> list[MemberOut]:
    need(session, user, project_id, "owner")
    access.remove_member(session, project_id, user_id)
    return [MemberOut(user=_user(u), role=r) for u, r in access.list_members(session, project_id)]
