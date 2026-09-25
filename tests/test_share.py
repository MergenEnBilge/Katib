from pathlib import Path

from fastapi.testclient import TestClient

from katib import net
from katib.api.app import create_app
from katib.config import Settings

API = "/api/v1"


def test_a_local_only_server_says_it_cannot_be_reached(tmp_path: Path) -> None:
    with TestClient(create_app(Settings(storage={"data_dir": str(tmp_path)}))) as c:
        body = c.get(f"{API}/share").json()
    assert body == {"reachable": False, "accounts": False, "urls": [], "secure": False}


def test_a_shared_server_lists_addresses_with_its_port(tmp_path: Path) -> None:
    settings = Settings(
        storage={"data_dir": str(tmp_path)},
        auth={"mode": "local"},
        server={"host": "0.0.0.0", "port": 9001},
    )
    with TestClient(create_app(settings)) as c:
        c.post(
            f"{API}/auth/setup",
            json={"email": "a@example.com", "name": "A", "password": "correct horse battery"},
        )
        body = c.get(f"{API}/share").json()
    assert body["reachable"] is True and body["accounts"] is True
    assert all(url.endswith(":9001") for url in body["urls"])


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
