import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage

API = "/api/v1"


@pytest.fixture
def image(client: TestClient, tmp_path: Path) -> tuple[str, str]:
    """A project that uses boxes and text, with one picture. Returns the project and image ids."""
    project = client.post(
        f"{API}/projects", json={"name": "Signs", "annotation_types": ["box", "text"]}
    ).json()
    picture = tmp_path / "a.png"
    PILImage.new("RGB", (40, 20), "white").save(picture)
    image_id = client.post(
        f"{API}/projects/{project['id']}/images",
        files={"file": ("a.png", picture.read_bytes(), "image/png")},
    ).json()["id"]
    return str(project["id"]), str(image_id)


def send(client: TestClient, image_id: str, *ops: dict[str, Any]) -> list[dict[str, Any]]:
    reply = client.post(f"{API}/images/{image_id}/annotations:batch", json={"ops": list(ops)})
    return list(reply.json()["results"])


def make(kind: str, geometry: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"op": "create", "id": str(uuid.uuid4()), "type": kind, "geometry": geometry, **extra}


def test_text_can_stand_alone_without_a_class(client: TestClient, image: tuple[str, str]) -> None:
    [result] = send(client, image[1], make("text", {"text": "A red bicycle by a wall."}))
    assert result["status"] == "ok"
    assert result["annotation"]["class_id"] is None
    saved = client.get(f"{API}/images/{image[1]}/annotations").json()
    assert saved[0]["geometry"] == {"text": "A red bicycle by a wall."}


def test_a_box_still_needs_a_class(client: TestClient, image: tuple[str, str]) -> None:
    box = {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}
    [result] = send(client, image[1], make("box", box))
    assert result["status"] == "invalid"


def test_text_can_be_edited_and_emptied(client: TestClient, image: tuple[str, str]) -> None:
    created = make("text", {"text": "first"})
    send(client, image[1], created)
    [result] = send(
        client,
        image[1],
        {"op": "update", "id": created["id"], "patch": {"geometry": {"text": ""}}},
    )
    assert result["status"] == "ok"
    assert result["annotation"]["geometry"] == {"text": ""}


def test_very_long_text_is_refused(client: TestClient, image: tuple[str, str]) -> None:
    [result] = send(client, image[1], make("text", {"text": "x" * 5001}))
    assert result["status"] == "invalid"


def test_a_box_can_carry_a_transcription(client: TestClient, image: tuple[str, str]) -> None:
    cls = client.post(f"{API}/projects/{image[0]}/classes", json={"name": "sign"}).json()
    box = {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}
    [ok] = send(
        client,
        image[1],
        make("box", box, class_id=cls["id"], attrs={"transcription": "STOP"}),
    )
    assert ok["status"] == "ok"
    assert ok["annotation"]["attrs"] == {"transcription": "STOP"}
    [bad] = send(
        client, image[1], make("box", box, class_id=cls["id"], attrs={"transcription": "x" * 5001})
    )
    assert bad["status"] == "invalid"


def test_text_needs_the_project_to_opt_in(client: TestClient, tmp_path: Path) -> None:
    project = client.post(f"{API}/projects", json={"name": "Boxes only"}).json()
    picture = tmp_path / "b.png"
    PILImage.new("RGB", (8, 8), "red").save(picture)
    image_id = client.post(
        f"{API}/projects/{project['id']}/images",
        files={"file": ("b.png", picture.read_bytes(), "image/png")},
    ).json()["id"]
    [result] = send(client, image_id, make("text", {"text": "hello"}))
    assert result["status"] == "invalid"
    assert "does not use text" in result["error"]
