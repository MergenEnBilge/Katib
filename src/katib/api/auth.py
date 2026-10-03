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
from katib.api.share import APP_DOWNLOAD_URL, share_urls
from katib.config import Settings, is_loopback
from katib.db.models import User
from katib.services import access, auth, setup_code
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
    #: True when the first account must be created with the code from the server's log.
    needs_setup_code: bool = False
    user: UserOut | None


class SetupIn(BaseModel):
    email: str
    name: str = ""
    password: str
    setup_code: str = ""


class LoginIn(BaseModel):
    email: str
    password: str


class InviteIn(BaseModel):
    project_id: uuid.UUID | None = None
    role: Literal["manager", "annotator", "reviewer", "viewer"] = "annotator"


class InviteOut(BaseModel):
    token: str
    path: str
    #: The whole link to send, built from an address other people can actually reach.
    url: str = ""


class InviteInfoOut(BaseModel):
    project: str | None
    role: str
    #: Where the phone app can be downloaded, for someone opening this on a phone without it.
    app_url: str = ""


class AcceptIn(BaseModel):
    token: str
    email: str
    name: str = ""
    password: str


class JoinOut(BaseModel):
    project_id: uuid.UUID


class PersonOut(BaseModel):
    """Just enough to pick someone from a list, for people who are not administrators."""

    id: uuid.UUID
    name: str
    email: str


class UserProjectOut(BaseModel):
    project_id: uuid.UUID
    name: str
    role: str


class TokenIn(BaseModel):
    name: str


class TokenOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    last_used_at: datetime | None
    token: str | None = None


class NewUserIn(BaseModel):
    email: str
    name: str = ""
    password: str
    is_admin: bool = False


class PasswordIn(BaseModel):
    password: str


class OwnPasswordIn(BaseModel):
    current_password: str
    new_password: str


class AdminIn(BaseModel):
    is_admin: bool


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


def _needs_code(request: Request) -> bool:
    settings = _settings(request)
    return setup_code.needs_code(
        client_address(request),
        request.headers,
        settings.server.behind_proxy,
        on_a_network=not is_loopback(settings.server.host),
    )


@router.get("/auth/status", response_model=StatusOut)
def status(request: Request, session: SessionDep) -> StatusOut:
    settings = _settings(request)
    user = find_user(request, session)
    needs_setup = settings.auth.mode == "local" and not auth.has_users(session)
    return StatusOut(
        mode=settings.auth.mode,
        needs_setup=needs_setup,
        needs_setup_code=needs_setup and _needs_code(request),
        user=_user(user) if user else None,
    )


@router.post("/auth/setup", response_model=UserOut, status_code=201)
def setup(
    body: SetupIn,
    request: Request,
    response: Response,
    session: SessionDep,
    limiter: LimiterDep,
) -> UserOut:
    settings = _settings(request)
    if settings.auth.mode != "local":
        raise Forbidden('Accounts are off. Turn on auth.mode = "local" to create them.')
    address = client_address(request)
    if _needs_code(request):
        key = f"setup:{address}"
        wait = limiter.retry_after(key)
        if wait:
            raise TooManyAttempts(
                f"Too many attempts. Try again in {wait} seconds.", retry_after=wait
            )
        if not setup_code.matches(settings.data_dir, body.setup_code):
            limiter.fail(key)
            raise Forbidden(
                "Other people can reach this server, and whoever makes this account runs it, "
                "so it needs its setup code. You will find it in the server's log, or in "
                "setup-code.txt in its data folder."
            )
    user = auth.setup_first_admin(session, body.email, body.name, body.password)
    setup_code.clear(settings.data_dir)
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
    return InviteInfoOut(project=info["project"], role=str(info["role"]), app_url=APP_DOWNLOAD_URL)


@router.post("/auth/accept", response_model=UserOut, status_code=201)
def accept(body: AcceptIn, request: Request, response: Response, session: SessionDep) -> UserOut:
    user = auth.accept_invite(session, body.token, body.email, body.name, body.password)
    _, token = auth.login(session, body.email, body.password)
    _set_cookie(request, response, token)
    return _user(user)


@router.post("/auth/invites/{token}:join", response_model=JoinOut)
def join(token: str, session: SessionDep, user: UserDep) -> JoinOut:
    """Someone who already has an account opens an invite: add them, no new account needed."""
    return JoinOut(project_id=auth.join_invite(session, token, user))


@router.post("/invites", response_model=InviteOut, status_code=201)
def create_invite(
    body: InviteIn, request: Request, session: SessionDep, user: UserDep
) -> InviteOut:
    if body.project_id is None:
        if not user.is_admin:
            raise Forbidden("Only administrators can invite people without a project.")
    else:
        role = access.require(session, user, body.project_id, "manage")
        if not access.can_assign(role, None, body.role):
            raise Forbidden("Only an owner can invite a manager.")
    token = auth.create_invite(session, user, body.project_id, body.role)
    path = f"/invite/{token}"
    # The whole point of an invite is that somebody else opens it, so it must not carry the address
    # the administrator happens to be using. "localhost" helps nobody.
    urls = share_urls(request)
    return InviteOut(token=token, path=path, url=f"{urls[0]}{path}" if urls else "")


@router.post("/auth/password", response_model=UserOut)
def change_password(
    body: OwnPasswordIn,
    request: Request,
    response: Response,
    session: SessionDep,
    user: UserDep,
    limiter: LimiterDep,
) -> UserOut:
    """Change your own password. Anyone handed one by an administrator should."""
    key = f"password:{user.id}"
    wait = limiter.retry_after(key)
    if wait:
        raise TooManyAttempts(f"Too many attempts. Try again in {wait} seconds.", retry_after=wait)
    try:
        token = auth.change_own_password(session, user, body.current_password, body.new_password)
    except Unauthorized:
        limiter.fail(key)
        raise
    limiter.reset(key)
    _set_cookie(request, response, token)
    return _user(user)


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


@router.post("/users", response_model=UserOut, status_code=201)
def create_person(body: NewUserIn, request: Request, session: SessionDep, user: UserDep) -> UserOut:
    """Make an account outright, for a team that would rather hand out logins than send invites."""
    if not user.is_admin:
        raise Forbidden("Only administrators can create accounts.")
    if _settings(request).auth.mode != "local":
        raise Forbidden("Accounts are off, so there is nobody to create. Turn them on first.")
    made = auth.create_user(session, body.email, body.name, body.password, is_admin=body.is_admin)
    return _user(made)


@router.post("/users/{user_id}:password", response_model=UserOut)
def set_password(
    user_id: uuid.UUID, body: PasswordIn, session: SessionDep, user: UserDep
) -> UserOut:
    if not user.is_admin:
        raise Forbidden("Only administrators can change someone else's password.")
    return _user(auth.set_password(session, user_id, body.password))


@router.post("/users/{user_id}:admin", response_model=UserOut)
def set_admin(user_id: uuid.UUID, body: AdminIn, session: SessionDep, user: UserDep) -> UserOut:
    if not user.is_admin:
        raise Forbidden("Only administrators can make someone an administrator.")
    return _user(auth.set_admin(session, user_id, body.is_admin, user))


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
    """Add someone who already has an account, or change their role."""
    access.require_assign(session, user, project_id, user_id, body.role)
    if user_id == user.id and body.role != "owner" and not user.is_admin:
        raise InvalidInput("You cannot remove your own ownership. Ask another owner.")
    access.add_member(session, project_id, user_id, body.role)
    return [MemberOut(user=_user(u), role=r) for u, r in access.list_members(session, project_id)]


@router.delete("/projects/{project_id}/members/{user_id}", response_model=list[MemberOut])
def remove_member(
    project_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep, user: UserDep
) -> list[MemberOut]:
    access.require_assign(session, user, project_id, user_id, None)
    access.remove_member(session, project_id, user_id)
    return [MemberOut(user=_user(u), role=r) for u, r in access.list_members(session, project_id)]


@router.get("/projects/{project_id}/people", response_model=list[PersonOut])
def addable_people(
    project_id: uuid.UUID, session: SessionDep, user: UserDep, q: str = ""
) -> list[PersonOut]:
    """Accounts on this server that could be added to the project. Administrators can search
    everyone; anyone else finds a person only by typing their whole email address."""
    need(session, user, project_id, "manage")
    return [
        PersonOut(id=p.id, name=p.name, email=p.email)
        for p in access.addable_people(session, project_id, q, exact_email=not user.is_admin)
    ]


@router.get("/users/{user_id}/projects", response_model=list[UserProjectOut])
def user_projects(user_id: uuid.UUID, session: SessionDep, user: UserDep) -> list[UserProjectOut]:
    if not user.is_admin:
        raise Forbidden("Only administrators can see everyone's projects.")
    return [
        UserProjectOut(project_id=p.id, name=p.name, role=r)
        for p, r in access.projects_of(session, user_id)
    ]
