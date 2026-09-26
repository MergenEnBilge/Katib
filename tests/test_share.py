from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from katib import net
from katib.api.app import create_app
from katib.config import Settings

API = "/api/v1"


def shared_settings(tmp_path: Path) -> Settings:
    return Settings(
        storage={"data_dir": str(tmp_path)},
        auth={"mode": "local"},
        server={"host": "0.0.0.0", "port": 9001},
    )


def sign_up(client: TestClient) -> None:
    client.post(
        f"{API}/auth/setup",
        json={"email": "a@example.com", "name": "A", "password": "correct horse battery"},
    )


def test_a_local_only_server_says_it_cannot_be_reached(tmp_path: Path) -> None:
    with TestClient(create_app(Settings(storage={"data_dir": str(tmp_path)}))) as c:
        body = c.get(f"{API}/share").json()
    assert body["reachable"] is False
    assert body["urls"] == []


def test_the_address_shared_is_the_one_the_browser_used(tmp_path: Path) -> None:
    """Inside a container, asking the system for its own address gives one only Docker can reach.
    The address this request arrived on is known to work."""
    with TestClient(create_app(shared_settings(tmp_path))) as c:
        sign_up(c)
        body = c.get(f"{API}/share", headers={"host": "192.168.1.20:8420"}).json()
    assert body["reachable"] is True and body["accounts"] is True
    assert body["urls"] == ["http://192.168.1.20:8420"]


def test_a_browser_on_the_server_itself_falls_back_to_the_network_address(tmp_path: Path) -> None:
    with TestClient(create_app(shared_settings(tmp_path))) as c:
        sign_up(c)
        body = c.get(f"{API}/share", headers={"host": "localhost:9001"}).json()
    assert all(url.endswith(":9001") for url in body["urls"])
    assert not any("localhost" in url for url in body["urls"])


def test_katib_asks_for_an_address_when_it_cannot_work_one_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In Docker the only address Katib can see is the container's, which nobody can reach. The
    share window has to ask rather than claim the server is closed."""
    monkeypatch.setattr(net, "in_container", lambda: True)
    with TestClient(create_app(shared_settings(tmp_path))) as c:
        sign_up(c)
        body = c.get(f"{API}/share", headers={"host": "localhost:9001"}).json()
    assert body["urls"] == []
    assert body["needs_address"] is True
    assert body["port"] == 9001


def test_a_server_closed_to_the_network_does_not_ask_for_an_address(tmp_path: Path) -> None:
    with TestClient(create_app(Settings(storage={"data_dir": str(tmp_path)}))) as c:
        body = c.get(f"{API}/share").json()
    assert body["needs_address"] is False


def test_an_invite_link_carries_an_address_other_people_can_open(tmp_path: Path) -> None:
    with TestClient(create_app(shared_settings(tmp_path))) as c:
        sign_up(c)
        project = c.post(f"{API}/projects", json={"name": "P"}).json()["id"]
        made = c.post(
            f"{API}/invites",
            json={"project_id": project, "role": "annotator"},
            headers={"host": "192.168.1.20:8420"},
        ).json()
    assert made["url"] == f"http://192.168.1.20:8420/invite/{made['token']}"


def test_a_public_address_wins_and_counts_as_secure(tmp_path: Path) -> None:
    settings = Settings(
        storage={"data_dir": str(tmp_path)}, server={"public_url": "https://katib.example.com/"}
    )
    with TestClient(create_app(settings)) as c:
        body = c.get(f"{API}/share").json()
    assert body["urls"] == ["https://katib.example.com"]
    assert body["secure"] is True


def test_qr_code_is_an_svg(tmp_path: Path) -> None:
    with TestClient(create_app(Settings(storage={"data_dir": str(tmp_path)}))) as c:
        res = c.get(f"{API}/share/qr.svg", params={"text": "http://192.168.1.4:8420"})
        too_long = c.get(f"{API}/share/qr.svg", params={"text": "x" * 400})
    assert res.headers["content-type"] == "image/svg+xml"
    assert "<svg" in res.text
    assert too_long.status_code == 422


def test_anyone_who_can_invite_can_make_a_code(tmp_path: Path) -> None:
    """A manager invites people to their own project without being an administrator, and the
    phone invite is a code to scan."""
    with TestClient(create_app(shared_settings(tmp_path))) as admin:
        sign_up(admin)
        project = admin.post(f"{API}/projects", json={"name": "P"}).json()["id"]
        token = admin.post(
            f"{API}/invites", json={"project_id": project, "role": "manager"}
        ).json()["token"]
        manager = TestClient(admin.app)
        manager.post(
            f"{API}/auth/accept",
            json={
                "token": token,
                "email": "m@example.com",
                "name": "M",
                "password": "correct horse battery",
            },
        )
        code = manager.get(f"{API}/share/qr.svg", params={"text": "http://192.168.1.20:8420"})
        closed = manager.get(f"{API}/share")
    assert code.status_code == 200
    assert closed.status_code == 403  # the addresses themselves stay with administrators


def test_an_invite_says_where_the_phone_app_comes_from(tmp_path: Path) -> None:
    with TestClient(create_app(shared_settings(tmp_path))) as c:
        sign_up(c)
        project = c.post(f"{API}/projects", json={"name": "P"}).json()["id"]
        token = c.post(f"{API}/invites", json={"project_id": project, "role": "viewer"}).json()[
            "token"
        ]
        info = c.get(f"{API}/auth/invites/{token}").json()
    assert info["app_url"].endswith(".apk")


def test_lan_addresses_never_include_loopback() -> None:
    assert not [a for a in net.lan_addresses() if a.startswith("127.")]
