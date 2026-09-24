import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from katib.auth.passwords import hash_password, hash_token, verify_password
from katib.auth.ratelimit import LoginLimiter
from katib.db.base import utcnow
from katib.db.models import AuthSession, Invite, ProjectMember
from katib.services import access, auth, projects
from katib.services.errors import EmailTaken, Forbidden, InvalidInput, NotFound, Unauthorized

PASSWORD = "correct horse battery"


def test_password_hashing() -> None:
    stored = hash_password(PASSWORD)
    assert stored.startswith("$argon2id$") and PASSWORD not in stored
    assert verify_password(stored, PASSWORD)
    assert not verify_password(stored, "wrong password!")
    assert not verify_password(None, PASSWORD)
    assert not verify_password("not a hash", PASSWORD)


def test_setup_only_works_once(session: Session) -> None:
    assert not auth.has_users(session)
    admin = auth.setup_first_admin(session, "Ada@Example.com", "Ada", PASSWORD)
    assert admin.is_admin and admin.email == "ada@example.com"
    with pytest.raises(Exception, match="already"):
        auth.setup_first_admin(session, "b@example.com", "B", PASSWORD)


def test_the_implicit_local_user_does_not_count_as_an_account(session: Session) -> None:
    local = auth.local_user(session)
    assert local.is_admin and auth.local_user(session).id == local.id
    assert not auth.has_users(session)


@pytest.mark.parametrize("email", ["", "nope", "a@b", "a b@c.d"])
def test_bad_emails_are_rejected(session: Session, email: str) -> None:
    with pytest.raises(InvalidInput):
        auth.create_user(session, email, "X", PASSWORD)


def test_short_passwords_and_duplicate_emails_are_rejected(session: Session) -> None:
    with pytest.raises(InvalidInput, match="at least 10"):
        auth.create_user(session, "a@example.com", "A", "short")
    auth.create_user(session, "a@example.com", "A", PASSWORD)
    with pytest.raises(EmailTaken):
        auth.create_user(session, "A@example.com", "A2", PASSWORD)


def test_login_logout_and_session_expiry(session: Session) -> None:
    user = auth.create_user(session, "a@example.com", "A", PASSWORD)
    with pytest.raises(Unauthorized, match="do not match"):
        auth.login(session, "a@example.com", "wrong password!")
    with pytest.raises(Unauthorized, match="do not match"):
        auth.login(session, "nobody@example.com", PASSWORD)

    _, token = auth.login(session, "A@example.com", PASSWORD)
    assert auth.user_for_session(session, token) == user
    row = session.scalars(select(AuthSession)).one()
    assert row.token_hash == hash_token(token) and token not in row.token_hash

    row.expires_at = utcnow() - timedelta(seconds=1)
    assert auth.user_for_session(session, token) is None
    row.expires_at = utcnow() + timedelta(days=1)
    auth.logout(session, token)
    assert auth.user_for_session(session, token) is None
    assert auth.user_for_session(session, "garbage") is None


def test_disabled_accounts_cannot_log_in_and_lose_sessions(session: Session) -> None:
    admin = auth.create_user(session, "admin@example.com", "Admin", PASSWORD, is_admin=True)
    user = auth.create_user(session, "u@example.com", "U", PASSWORD)
    _, token = auth.login(session, "u@example.com", PASSWORD)
    auth.set_disabled(session, user.id, True, admin)
    assert auth.user_for_session(session, token) is None
    with pytest.raises(Unauthorized):
        auth.login(session, "u@example.com", PASSWORD)
    with pytest.raises(InvalidInput):
        auth.set_disabled(session, admin.id, True, admin)


def test_invites_are_single_use_expire_and_add_a_member(session: Session) -> None:
    admin = auth.create_user(session, "admin@example.com", "Admin", PASSWORD, is_admin=True)
    project = projects.create_project(session, "P")
    token = auth.create_invite(session, admin, project.id, "reviewer")
    assert session.scalars(select(Invite)).one().token_hash == hash_token(token)
    assert auth.invite_info(session, token) == {"project": "P", "role": "reviewer"}

    user = auth.accept_invite(session, token, "new@example.com", "New", PASSWORD)
    member = session.get(ProjectMember, (project.id, user.id))
    assert member is not None and member.role == "reviewer" and not user.is_admin
    with pytest.raises(auth.InviteInvalid):
        auth.accept_invite(session, token, "other@example.com", "O", PASSWORD)

    expired = auth.create_invite(session, admin, None, "viewer")
    session.scalars(select(Invite).where(Invite.used_at.is_(None))).one().expires_at = (
        utcnow() - timedelta(minutes=1)
    )
    with pytest.raises(auth.InviteInvalid):
        auth.invite_info(session, expired)
    with pytest.raises(InvalidInput):
        auth.create_invite(session, admin, None, "owner")


def test_api_tokens_are_shown_once_and_can_be_revoked(session: Session) -> None:
    user = auth.create_user(session, "a@example.com", "A", PASSWORD)
    row, token = auth.create_api_token(session, user, "ci")
    assert token.startswith("kb_") and row.token_hash == hash_token(token)
    assert auth.user_for_api_token(session, token) == user
    assert [t.id for t in auth.list_api_tokens(session, user)] == [row.id]
    auth.revoke_api_token(session, user, row.id)
    assert auth.user_for_api_token(session, token) is None
    with pytest.raises(NotFound):
        auth.revoke_api_token(session, user, uuid.uuid4())


def test_roles_and_capabilities(session: Session) -> None:
    admin = auth.create_user(session, "admin@example.com", "Admin", PASSWORD, is_admin=True)
    project = projects.create_project(session, "P")
    other = projects.create_project(session, "Q")
    people = {
        role: auth.create_user(session, f"{role}@example.com", role, PASSWORD)
        for role in access.ROLES
    }
    for role, user in people.items():
        access.add_member(session, project.id, user.id, role)

    matrix = {
        "owner": {"view", "annotate", "review", "manage", "owner"},
        "manager": {"view", "annotate", "review", "manage"},
        "reviewer": {"view", "annotate", "review"},
        "annotator": {"view", "annotate"},
        "viewer": {"view"},
    }
    for role, allowed in matrix.items():
        for cap in ("view", "annotate", "review", "manage", "owner"):
            if cap in allowed:
                access.require(session, people[role], project.id, cap)  # type: ignore[arg-type]
            else:
                with pytest.raises(Forbidden):
                    access.require(session, people[role], project.id, cap)  # type: ignore[arg-type]

    with pytest.raises(NotFound):
        access.require(session, people["owner"], other.id, "view")
    assert access.require(session, admin, other.id, "owner") == "owner"
    assert access.visible_project_ids(session, admin) is None
    assert access.visible_project_ids(session, people["viewer"]) == {project.id}


def test_projects_need_an_owner(session: Session) -> None:
    project = projects.create_project(session, "P")
    boss = auth.create_user(session, "boss@example.com", "Boss", PASSWORD)
    access.add_member(session, project.id, boss.id, "owner")
    with pytest.raises(InvalidInput, match="at least one owner"):
        access.remove_member(session, project.id, boss.id)
    helper = auth.create_user(session, "h@example.com", "H", PASSWORD)
    access.add_member(session, project.id, helper.id, "annotator")
    access.remove_member(session, project.id, helper.id)
    assert [u.id for u, _ in access.list_members(session, project.id)] == [boss.id]


def test_login_limiter_blocks_then_recovers() -> None:
    now = [0.0]
    limiter = LoginLimiter(max_failures=3, window=60, clock=lambda: now[0])
    for _ in range(3):
        assert limiter.retry_after("a") == 0
        limiter.fail("a")
    assert limiter.retry_after("a") > 0
    assert limiter.retry_after("b") == 0
    now[0] = 61
    assert limiter.retry_after("a") == 0
    limiter.fail("a")
    limiter.reset("a")
    assert limiter.retry_after("a") == 0
