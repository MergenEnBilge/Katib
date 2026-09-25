from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage
from starlette.websockets import WebSocketDisconnect

from katib.api.app import create_app
from katib.config import Settings
from katib.storage.imaging import UnreadableImage, read_info

API = "/api/v1"
PASSWORD = "correct horse battery"


def shared_server(tmp_path: Path, **server: object) -> Settings:
    return Settings(
        storage={"data_dir": str(tmp_path / "data")}, auth={"mode": "local"}, server=server
    )


def sign_up(client: TestClient) -> None:
    res = client.post(
        f"{API}/auth/setup", json={"email": "a@example.com", "name": "A", "password": PASSWORD}
    )
    assert res.status_code == 201


def test_a_web_socket_from_another_site_is_refused(tmp_path: Path) -> None:
    with TestClient(create_app(shared_server(tmp_path))) as client:
        sign_up(client)
        project = client.post(f"{API}/projects", json={"name": "P"}).json()["id"]

        with (
            pytest.raises(WebSocketDisconnect) as refused,
            client.websocket_connect(
                f"{API}/ws?project={project}", headers={"origin": "https://evil.example"}
            ),
        ):
            pass
        assert refused.value.code == 4403

        with client.websocket_connect(
            f"{API}/ws?project={project}", headers={"origin": "http://testserver"}
        ) as fine:
            # The first message is the list of who is here, which proves the connection opened.
            assert fine.receive_json()["type"] == "presence"


def test_the_cookie_is_secure_when_a_trusted_proxy_says_https(tmp_path: Path) -> None:
    with TestClient(create_app(shared_server(tmp_path, behind_proxy=True))) as client:
        res = client.post(
            f"{API}/auth/setup",
            json={"email": "a@example.com", "name": "A", "password": PASSWORD},
            headers={"x-forwarded-proto": "https"},
        )
    assert "secure" in res.headers["set-cookie"].lower()


def test_forwarded_headers_are_ignored_unless_a_proxy_is_trusted(tmp_path: Path) -> None:
    with TestClient(create_app(shared_server(tmp_path))) as client:
        res = client.post(
            f"{API}/auth/setup",
            json={"email": "a@example.com", "name": "A", "password": PASSWORD},
            headers={"x-forwarded-proto": "https"},
        )
    assert "secure" not in res.headers["set-cookie"].lower()


def test_failed_logins_are_counted_per_visitor_behind_a_proxy(tmp_path: Path) -> None:
    """One person guessing must not lock everyone else out just because they share the proxy."""
    with TestClient(create_app(shared_server(tmp_path, behind_proxy=True))) as client:
        sign_up(client)
        guesser = {"x-forwarded-for": "203.0.113.7"}
        for i in range(5):
            client.post(
                f"{API}/auth/login",
                json={"email": f"nobody{i}@example.com", "password": "wrong password here"},
                headers=guesser,
            )
        blocked = client.post(
            f"{API}/auth/login",
            json={"email": "other@example.com", "password": "wrong password here"},
            headers=guesser,
        )
        neighbour = client.post(
            f"{API}/auth/login",
            json={"email": "a@example.com", "password": PASSWORD},
            headers={"x-forwarded-for": "198.51.100.9"},
        )
    assert blocked.status_code == 429
    assert neighbour.status_code == 200


def test_a_picture_is_read_by_its_content_and_only_in_allowed_formats(tmp_path: Path) -> None:
    fine = tmp_path / "a.png"
    PILImage.new("RGB", (4, 4), "red").save(fine)
    assert read_info(fine).width == 4

    # A GIF renamed to .jpg is a real picture, but not one of the formats Katib supports.
    gif = tmp_path / "b.jpg"
    PILImage.new("P", (4, 4)).save(gif, "GIF")
    with pytest.raises(UnreadableImage):
        read_info(gif)


def test_where_models_live_is_shown_only_to_administrators(tmp_path: Path) -> None:
    settings = Settings(
        storage={"data_dir": str(tmp_path / "data")},
        auth={"mode": "local"},
        ml={"enabled": True, "models_dir": str(tmp_path / "models")},
    )
    with TestClient(create_app(settings)) as admin:
        sign_up(admin)
        project = admin.post(f"{API}/projects", json={"name": "P"}).json()["id"]
        invite = admin.post(f"{API}/invites", json={"project_id": project, "role": "viewer"}).json()
        viewer = TestClient(admin.app)
        viewer.post(
            f"{API}/auth/accept",
            json={
                "token": invite["token"],
                "email": "v@example.com",
                "name": "V",
                "password": PASSWORD,
            },
        )
        assert admin.get(f"{API}/ml").json()["models_dir"] == str(tmp_path / "models")
        assert viewer.get(f"{API}/ml").json()["models_dir"] == ""


def test_a_bad_import_path_is_refused_even_with_dots(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    settings = Settings(
        storage={"data_dir": str(tmp_path / "data"), "allowed_import_roots": [str(library)]}
    )
    with TestClient(create_app(settings)) as client:
        project = client.post(f"{API}/projects", json={"name": "P"}).json()["id"]
        sneaky = str(library / ".." / "data")
        res = client.post(f"{API}/projects/{project}/images:import-folder", json={"folder": sneaky})
    assert res.status_code == 403


def test_responses_switch_off_browser_features_katib_does_not_use(client: TestClient) -> None:
    headers = client.get("/api/v1/health").headers
    assert "camera=()" in headers["permissions-policy"]
    assert headers["cross-origin-opener-policy"] == "same-origin"
    assert "strict-transport-security" not in headers  # plain HTTP: HSTS would be ignored


def test_hsts_is_sent_only_over_https(client: TestClient) -> None:
    secure = client.get("/api/v1/health", headers={"x-forwarded-proto": "https"})
    assert "strict-transport-security" not in secure.headers  # a proxy header alone is not trusted


def test_hsts_is_sent_when_a_trusted_proxy_says_https(tmp_path: Path) -> None:
    settings = Settings(storage={"data_dir": str(tmp_path)}, server={"behind_proxy": True})
    with TestClient(create_app(settings)) as api:
        secure = api.get("/api/v1/health", headers={"x-forwarded-proto": "https"})
        assert "max-age=" in secure.headers["strict-transport-security"]
