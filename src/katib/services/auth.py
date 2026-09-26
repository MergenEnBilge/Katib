"""Accounts, browser sessions, invites and API tokens."""

import re
import uuid
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from katib.auth.passwords import (
    WeakPassword,
    check_strength,
    hash_password,
    hash_token,
    needs_rehash,
    new_token,
    verify_password,
)
from katib.db.base import utcnow
from katib.db.models import ApiToken, AuthSession, Invite, Project, ProjectMember, User
from katib.services.errors import (
    EmailTaken,
    InvalidInput,
    KatibError,
    NotFound,
    Unauthorized,
)

SESSION_DAYS = 14
INVITE_DAYS = 7
LOCAL_EMAIL = "local@katib.invalid"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLES = ("owner", "manager", "annotator", "reviewer", "viewer")


class InviteInvalid(KatibError):
    code = "invite_invalid"
    status = 410


def _email(value: str) -> str:
    email = value.strip().lower()
    if not _EMAIL.match(email) or len(email) > 320:
        raise InvalidInput("Enter a valid email address.")
    return email


def _name(value: str, email: str) -> str:
    name = value.strip() or email.split("@")[0]
    if len(name) > 200:
        raise InvalidInput("Names can be up to 200 characters.")
    return name


def has_users(session: Session) -> bool:
    """True once a real account exists. The implicit local user does not count."""
    count = session.scalar(select(func.count(User.id)).where(User.email != LOCAL_EMAIL))
    return bool(count)


def local_user(session: Session) -> User:
    """The implicit owner when auth is off. It is created on first use."""
    user = session.scalar(select(User).where(User.email == LOCAL_EMAIL))
    if user is None:
        user = User(email=LOCAL_EMAIL, name="You", password_hash=None, is_admin=True)
        session.add(user)
        session.flush()
    return user


def create_user(
    session: Session, email: str, name: str, password: str, *, is_admin: bool = False
) -> User:
    email = _email(email)
    try:
        check_strength(password)
    except WeakPassword as err:
        raise InvalidInput(str(err)) from err
    if session.scalar(select(User.id).where(User.email == email)) is not None:
        raise EmailTaken("An account with that email already exists.")
    user = User(
        email=email,
        name=_name(name, email),
        password_hash=hash_password(password),
        is_admin=is_admin,
    )
    session.add(user)
    session.flush()
    return user


def setup_first_admin(session: Session, email: str, name: str, password: str) -> User:
    """Create the first administrator. Only works while no account exists."""
    if has_users(session):
        raise KatibError("Setup has already been done.")
    return create_user(session, email, name, password, is_admin=True)


def login(session: Session, email: str, password: str) -> tuple[User, str]:
    """Check credentials and start a session. Returns the user and the cookie value."""
    user = session.scalar(select(User).where(User.email == email.strip().lower()))
    ok = verify_password(user.password_hash if user else None, password)
    if not ok or user is None or user.disabled_at is not None:
        raise Unauthorized("That email and password do not match.")
    if user.password_hash and needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    token = new_token()
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=utcnow() + timedelta(days=SESSION_DAYS),
        )
    )
    session.flush()
    return user, token


def user_for_session(session: Session, token: str) -> User | None:
    row = session.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    if row is None or row.expires_at <= utcnow():
        return None
    user = session.get(User, row.user_id)
    return user if user is not None and user.disabled_at is None else None


def logout(session: Session, token: str) -> None:
    session.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(token)))


def create_invite(
    session: Session,
    creator: User,
    project_id: uuid.UUID | None,
    role: str = "annotator",
) -> str:
    """Return a one-time token. It is shown once and only its hash is stored."""
    if role not in ROLES or role == "owner":
        raise InvalidInput("Choose a role: manager, annotator, reviewer or viewer.")
    if project_id is not None and session.get(Project, project_id) is None:
        raise NotFound("That project does not exist.")
    token = new_token()
    session.add(
        Invite(
            token_hash=hash_token(token),
            project_id=project_id,
            role=role,
            created_by=creator.id,
            expires_at=utcnow() + timedelta(days=INVITE_DAYS),
        )
    )
    session.flush()
    return token


def _invite(session: Session, token: str) -> Invite:
    invite = session.scalar(select(Invite).where(Invite.token_hash == hash_token(token)))
    if invite is None or invite.used_at is not None or invite.expires_at <= utcnow():
        raise InviteInvalid("This invite link has expired or was already used.")
    return invite


def invite_info(session: Session, token: str) -> dict[str, str | None]:
    invite = _invite(session, token)
    project = session.get(Project, invite.project_id) if invite.project_id else None
    return {"project": project.name if project else None, "role": invite.role}


def accept_invite(session: Session, token: str, email: str, name: str, password: str) -> User:
    invite = _invite(session, token)
    user = create_user(session, email, name, password)
    invite.used_at = utcnow()
    if invite.project_id is not None:
        session.add(ProjectMember(project_id=invite.project_id, user_id=user.id, role=invite.role))
    session.flush()
    return user


def create_api_token(session: Session, user: User, name: str) -> tuple[ApiToken, str]:
    name = name.strip()
    if not name:
        raise InvalidInput("Give the token a name.")
    token = "kb_" + new_token()
    row = ApiToken(user_id=user.id, name=name[:200], token_hash=hash_token(token))
    session.add(row)
    session.flush()
    return row, token


def user_for_api_token(session: Session, token: str) -> User | None:
    row = session.scalar(select(ApiToken).where(ApiToken.token_hash == hash_token(token)))
    if row is None or row.revoked_at is not None:
        return None
    user = session.get(User, row.user_id)
    if user is None or user.disabled_at is not None:
        return None
    row.last_used_at = utcnow()
    return user


def list_api_tokens(session: Session, user: User) -> list[ApiToken]:
    stmt = select(ApiToken).where(ApiToken.user_id == user.id, ApiToken.revoked_at.is_(None))
    return list(session.scalars(stmt.order_by(ApiToken.created_at.desc())))


def revoke_api_token(session: Session, user: User, token_id: uuid.UUID) -> None:
    row = session.get(ApiToken, token_id)
    if row is None or row.user_id != user.id:
        raise NotFound("That token does not exist.")
    row.revoked_at = utcnow()


def list_users(session: Session) -> list[User]:
    stmt = select(User).where(User.email != LOCAL_EMAIL).order_by(User.created_at)
    return list(session.scalars(stmt))


def _person(session: Session, user_id: uuid.UUID) -> User:
    """A real account. The implicit local user is not one anybody can administer."""
    user = session.get(User, user_id)
    if user is None or user.email == LOCAL_EMAIL:
        raise NotFound("That person does not exist.")
    return user


def set_password(session: Session, user_id: uuid.UUID, password: str) -> User:
    """Give someone a new password, usually because they have forgotten theirs."""
    user = _person(session, user_id)
    try:
        check_strength(password)
    except WeakPassword as err:
        raise InvalidInput(str(err)) from err
    user.password_hash = hash_password(password)
    # Anyone signed in with the old password is signed out, which is the point of changing it.
    session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    session.flush()
    return user


def set_admin(session: Session, user_id: uuid.UUID, is_admin: bool, actor: User) -> User:
    user = _person(session, user_id)
    if user.id == actor.id and not is_admin:
        raise InvalidInput(
            "You cannot take away your own administrator rights. Ask another administrator."
        )
    user.is_admin = is_admin
    session.flush()
    return user


def set_disabled(session: Session, user_id: uuid.UUID, disabled: bool, actor: User) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise NotFound("That person does not exist.")
    if user.id == actor.id:
        raise InvalidInput("You cannot disable your own account.")
    user.disabled_at = utcnow() if disabled else None
    if disabled:
        session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    session.flush()
    return user
