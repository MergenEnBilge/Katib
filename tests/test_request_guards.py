"""Other web pages and other people's servers must not be able to drive this Katib."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from katib.api.app import create_app
from katib.config import Settings

API = "/api/v1"


@pytest.fixture
def local(tmp_path: Path) -> Iterator[TestClient]:
    """Katib as it runs out of the box: loopback only, no accounts."""
    with TestClient(create_app(Settings(storage={"data_dir": str(tmp_path)}))) as client:
        yield client


def test_a_request_addressed_to_another_host_name_is_refused(local: TestClient) -> None:
    # DNS rebinding: a page on evil.example re-points its own name at 127.0.0.1.
    rebound = local.get(f"{API}/projects", headers={"host": "evil.example:8420"})
    assert rebound.status_code == 403
    assert "localhost" in rebound.json()["message"]
    assert local.get(f"{API}/projects", headers={"host": "localhost:8420"}).status_code == 200
    assert local.get(f"{API}/projects", headers={"host": "127.0.0.1:8420"}).status_code == 200
    assert local.get(f"{API}/projects", headers={"host": "[::1]:8420"}).status_code == 200


def test_a_cross_site_post_is_refused_even_without_a_cookie(local: TestClient) -> None:
    # With accounts off there is no session cookie, and the visitor counts as an administrator.
    evil = local.post(f"{API}/settings/restart", headers={"origin": "https://evil.example"})
    assert evil.status_code == 403
    assert "another site" in evil.json()["message"]
    # A script with no Origin header, such as the Python client, is not a browser page.
    assert local.post(f"{API}/projects", json={"name": "From a script"}).status_code == 201
    same = local.post(
        f"{API}/projects", json={"name": "Same site"}, headers={"origin": "http://testserver"}
    )
    assert same.status_code == 201


def test_a_shared_server_answers_to_its_network_address(tmp_path: Path) -> None:
    settings = Settings(
        storage={"data_dir": str(tmp_path)},
        server={"host": "0.0.0.0"},  # noqa: S104
        auth={"mode": "local"},
    )
    with TestClient(create_app(settings)) as client:
        assert client.get(f"{API}/health", headers={"host": "192.168.1.20:8420"}).status_code == 200


def test_a_rebound_websocket_is_refused(local: TestClient) -> None:
    project = local.post(f"{API}/projects", json={"name": "P"}).json()["id"]
    with (
        pytest.raises(WebSocketDisconnect) as closed,
        local.websocket_connect(
            f"{API}/ws?project={project}",
            headers={"host": "evil.example:8420", "origin": "http://evil.example:8420"},
        ) as ws,
    ):
        ws.receive_json()
    assert closed.value.code == 4403
