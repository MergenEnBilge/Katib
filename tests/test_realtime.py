import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from katib.api.app import create_app
from katib.config import Settings

API = "/api/v1"
PASSWORD = "correct horse battery"


@pytest.fixture
def admin(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(storage={"data_dir": str(tmp_path / "data")}, auth={"mode": "local"})
    with TestClient(create_app(settings)) as c:
        c.post(
            f"{API}/auth/setup",
            json={"email": "admin@example.com", "name": "Admin", "password": PASSWORD},
        )
        yield c


def next_of(ws: Any, kind: str) -> dict[str, Any]:
    for _ in range(20):
        message = ws.receive_json()
        if message["type"] == kind:
            return message  # type: ignore[no-any-return]
    raise AssertionError(f"no {kind} message")


def test_presence_and_viewing(admin: TestClient) -> None:
    pid = admin.post(f"{API}/projects", json={"name": "P"}).json()["id"]
    token = admin.post(f"{API}/invites", json={"project_id": pid, "role": "annotator"}).json()[
        "token"
    ]
    sam = TestClient(admin.app)
    sam.post(
        f"{API}/auth/accept",
        json={"token": token, "email": "sam@example.com", "name": "Sam", "password": PASSWORD},
    )
    with admin.websocket_connect(f"{API}/ws?project={pid}") as a:
        assert [u["name"] for u in next_of(a, "presence")["users"]] == ["Admin"]
        with sam.websocket_connect(f"{API}/ws?project={pid}") as b:
            names = sorted(u["name"] for u in next_of(a, "presence")["users"])
            assert names == ["Admin", "Sam"]
            image = str(uuid.uuid4())
            b.send_json({"type": "viewing", "image_id": image})
            update = next_of(a, "presence")
            assert {u["name"]: u["image_id"] for u in update["users"]}["Sam"] == image
            b.send_json({"type": "ping"})
            assert next_of(b, "pong")
        left = next_of(a, "presence")
        assert [u["name"] for u in left["users"]] == ["Admin"]


def test_strangers_and_outsiders_are_refused(admin: TestClient) -> None:
    pid = admin.post(f"{API}/projects", json={"name": "P"}).json()["id"]
    with (
        pytest.raises(WebSocketDisconnect),
        TestClient(admin.app).websocket_connect(f"{API}/ws?project={pid}"),
    ):
        pass

    token = admin.post(f"{API}/invites", json={}).json()["token"]
    outsider = TestClient(admin.app)
    outsider.post(
        f"{API}/auth/accept",
        json={"token": token, "email": "o@example.com", "name": "O", "password": PASSWORD},
    )
    with pytest.raises(WebSocketDisconnect), outsider.websocket_connect(f"{API}/ws?project={pid}"):
        pass


def test_events_are_published_after_a_write(admin: TestClient) -> None:
    pid = admin.post(f"{API}/projects", json={"name": "P"}).json()["id"]
    with admin.websocket_connect(f"{API}/ws?project={pid}") as ws:
        next_of(ws, "presence")
        admin.post(f"{API}/projects/{pid}/classes", json={"name": "car"})
        assert next_of(ws, "class.changed")
        admin.post(f"{API}/projects/{pid}/classes", json={"name": "car"})  # rejected: no event
        admin.post(f"{API}/projects/{pid}/classes", json={"name": "bus"})
        assert next_of(ws, "class.changed")
