from pathlib import Path

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


def test_lan_addresses_never_include_loopback() -> None:
    assert not [a for a in net.lan_addresses() if a.startswith("127.")]
