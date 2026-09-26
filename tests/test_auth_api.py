import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from katib.api.app import create_app
from katib.config import Settings

API = "/api/v1"
PASSWORD = "correct horse battery"


@pytest.fixture
def app_settings(tmp_path: Path) -> Settings:
    return Settings(storage={"data_dir": str(tmp_path / "data")}, auth={"mode": "local"})


@pytest.fixture
def admin(app_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(app_settings)) as c:
        res = c.post(
            f"{API}/auth/setup",
            json={"email": "admin@example.com", "name": "Admin", "password": PASSWORD},
        )
        assert res.status_code == 201, res.text
        yield c


def client_for(admin: TestClient) -> TestClient:
    """A second browser on the same server, with its own cookies."""
    return TestClient(admin.app)


def invite(admin: TestClient, project_id: str, role: str) -> str:
    res = admin.post(f"{API}/invites", json={"project_id": project_id, "role": role})
    assert res.status_code == 201, res.text
    return str(res.json()["token"])


def join(admin: TestClient, project_id: str, role: str, email: str) -> TestClient:
    person = client_for(admin)
    token = invite(admin, project_id, role)
    res = person.post(
        f"{API}/auth/accept",
        json={"token": token, "email": email, "name": role, "password": PASSWORD},
    )
    assert res.status_code == 201, res.text
    return person


def test_everything_needs_a_login_and_setup_happens_once(app_settings: Settings) -> None:
    with TestClient(create_app(app_settings)) as c:
        status = c.get(f"{API}/auth/status").json()
        assert status == {
            "mode": "local",
            "needs_setup": True,
            "needs_setup_code": False,
            "user": None,
        }
        assert c.get(f"{API}/projects").status_code == 401
        assert c.get(f"{API}/projects").json()["code"] == "unauthorized"
        assert c.get(f"{API}/health").status_code == 200

        res = c.post(f"{API}/auth/setup", json={"email": "a@example.com", "password": PASSWORD})
        cookie = res.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=lax" in cookie
        assert c.get(f"{API}/auth/status").json()["needs_setup"] is False
        assert c.get(f"{API}/projects").status_code == 200
        again = TestClient(c.app).post(
            f"{API}/auth/setup", json={"email": "b@example.com", "password": PASSWORD}
        )
        assert again.status_code == 400 and "already" in again.json()["message"]


def test_setup_is_refused_when_auth_is_off(tmp_path: Path) -> None:
    with TestClient(create_app(Settings(storage={"data_dir": str(tmp_path)}))) as c:
        assert (
            c.post(f"{API}/auth/setup", json={"email": "a@b.co", "password": PASSWORD}).status_code
            == 403
        )
        assert c.get(f"{API}/auth/status").json()["user"]["is_admin"] is True


def test_security_headers(admin: TestClient) -> None:
    res = admin.get(f"{API}/health")
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["referrer-policy"] == "same-origin"
    assert "default-src 'self'" in res.headers["content-security-policy"]
    assert res.headers["x-frame-options"] == "DENY"


def test_login_logout_and_rate_limit(admin: TestClient) -> None:
    other = client_for(admin)
    bad = other.post(
        f"{API}/auth/login", json={"email": "admin@example.com", "password": "nope nope nope"}
    )
    assert bad.status_code == 401
    assert "do not match" in bad.json()["message"]
    ok = other.post(f"{API}/auth/login", json={"email": "admin@example.com", "password": PASSWORD})
    assert ok.status_code == 200 and other.get(f"{API}/projects").status_code == 200
    assert other.post(f"{API}/auth/logout").status_code == 204
    assert other.get(f"{API}/projects").status_code == 401

    victim = client_for(admin)
    for _ in range(5):
        victim.post(
            f"{API}/auth/login",
            json={"email": "admin@example.com", "password": "guess guess guess"},
        )
    blocked = victim.post(
        f"{API}/auth/login", json={"email": "admin@example.com", "password": PASSWORD}
    )
    assert blocked.status_code == 429
    assert blocked.json()["details"]["retry_after"] > 0


def test_cross_site_writes_with_a_cookie_are_blocked(admin: TestClient) -> None:
    body = {"name": "Nope"}
    evil = admin.post(f"{API}/projects", json=body, headers={"Origin": "https://evil.example"})
    assert evil.status_code == 403
    same = admin.post(f"{API}/projects", json=body, headers={"Origin": "http://testserver"})
    assert same.status_code == 201


def test_api_tokens_work_as_bearer_and_can_be_revoked(admin: TestClient) -> None:
    made = admin.post(f"{API}/auth/tokens", json={"name": "ci"}).json()
    assert made["token"].startswith("kb_")
    listed = admin.get(f"{API}/auth/tokens").json()
    assert listed[0]["token"] is None and listed[0]["name"] == "ci"

    script = client_for(admin)
    headers = {"Authorization": f"Bearer {made['token']}"}
    assert script.get(f"{API}/projects", headers=headers).status_code == 200
    assert (
        script.get(f"{API}/projects", headers={"Authorization": "Bearer kb_wrong"}).status_code
        == 401
    )
    admin.delete(f"{API}/auth/tokens/{made['id']}")
    assert script.get(f"{API}/projects", headers=headers).status_code == 401


def test_roles_are_enforced_on_a_project(admin: TestClient) -> None:
    project = admin.post(f"{API}/projects", json={"name": "P"}).json()
    pid = project["id"]
    car = admin.post(f"{API}/projects/{pid}/classes", json={"name": "car"}).json()

    annotator = join(admin, pid, "annotator", "ann@example.com")
    viewer = join(admin, pid, "viewer", "view@example.com")
    outsider = client_for(admin)
    admin.post(
        f"{API}/invites", json={"role": "viewer"}
    )  # a project-less invite is fine for admins
    token = admin.post(f"{API}/invites", json={}).json()["token"]
    outsider.post(
        f"{API}/auth/accept",
        json={"token": token, "email": "out@example.com", "name": "Out", "password": PASSWORD},
    )

    assert [p["id"] for p in annotator.get(f"{API}/projects").json()] == [pid]
    assert outsider.get(f"{API}/projects").json() == []
    assert outsider.get(f"{API}/projects/{pid}").status_code == 404
    assert outsider.get(f"{API}/projects/{pid}/classes").status_code == 404

    assert annotator.get(f"{API}/projects/{pid}/classes").status_code == 200
    denied = annotator.post(f"{API}/projects/{pid}/classes", json={"name": "bus"})
    assert denied.status_code == 403 and denied.json()["code"] == "forbidden"
    assert annotator.delete(f"{API}/projects/{pid}").status_code == 403
    assert viewer.patch(f"{API}/projects/{pid}", json={"name": "X"}).status_code == 403

    members = admin.get(f"{API}/projects/{pid}/members").json()
    assert sorted(m["role"] for m in members) == ["annotator", "owner", "viewer"]
    assert annotator.get(f"{API}/projects/{pid}/members").status_code == 200
    assert (
        annotator.put(
            f"{API}/projects/{pid}/members/{uuid.uuid4()}", json={"role": "manager"}
        ).status_code
        == 403
    )
    assert car["name"] == "car"


def test_an_invite_link_works_once(admin: TestClient) -> None:
    project = admin.post(f"{API}/projects", json={"name": "P"}).json()
    token = invite(admin, project["id"], "reviewer")
    info = client_for(admin).get(f"{API}/auth/invites/{token}").json()
    assert info["project"] == "P"
    assert info["role"] == "reviewer"
    body = {"token": token, "email": "r@example.com", "name": "R", "password": PASSWORD}
    assert client_for(admin).post(f"{API}/auth/accept", json=body).status_code == 201
    second = client_for(admin).post(f"{API}/auth/accept", json={**body, "email": "s@example.com"})
    assert second.status_code == 410 and second.json()["code"] == "invite_invalid"
    assert client_for(admin).get(f"{API}/auth/invites/garbage").status_code == 410


def test_managers_can_invite_but_annotators_cannot(admin: TestClient) -> None:
    pid = admin.post(f"{API}/projects", json={"name": "P"}).json()["id"]
    manager = join(admin, pid, "manager", "m@example.com")
    annotator = join(admin, pid, "annotator", "a@example.com")
    assert (
        manager.post(f"{API}/invites", json={"project_id": pid, "role": "annotator"}).status_code
        == 201
    )
    assert (
        annotator.post(f"{API}/invites", json={"project_id": pid, "role": "viewer"}).status_code
        == 403
    )
    assert manager.post(f"{API}/invites", json={}).status_code == 403


def test_admin_can_disable_an_account(admin: TestClient) -> None:
    pid = admin.post(f"{API}/projects", json={"name": "P"}).json()["id"]
    person = join(admin, pid, "annotator", "a@example.com")
    people = admin.get(f"{API}/users").json()
    target = next(u for u in people if u["email"] == "a@example.com")
    assert person.get(f"{API}/users").status_code == 403
    assert admin.post(f"{API}/users/{target['id']}:disable").json()["disabled"] is True
    assert person.get(f"{API}/projects").status_code == 401
