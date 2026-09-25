import io
import json
import time
import uuid
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage

from katib.api.app import create_app
from katib.config import Settings

API = "/api/v1"


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    (tmp_path / "out").mkdir()
    settings = Settings(
        storage={
            "data_dir": str(tmp_path / "data"),
            "allowed_import_roots": [str(tmp_path / "out")],
        }
    )
    with TestClient(create_app(settings)) as c:
        yield c


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


def wait_job(client: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(300):
        job: dict[str, Any] = client.get(f"{API}/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_text_survives_an_export_and_an_import(
    client: TestClient, image: tuple[str, str], tmp_path: Path
) -> None:
    project, image_id = image
    sign = client.post(f"{API}/projects/{project}/classes", json={"name": "sign"}).json()
    box = {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}
    send(
        client,
        image_id,
        make("text", {"text": "A stop sign on a corner."}),
        make("text", {"text": "Second caption."}),
        make("box", box, class_id=sign["id"], attrs={"transcription": "STOP"}),
    )
    client.post(f"{API}/projects/{project}/splits:shuffle", json={"ratios": {"test": 1}})

    job = client.post(f"{API}/projects/{project}/exports", json={"format": "jsonl"}).json()
    done = wait_job(client, job["id"])
    assert done["status"] == "done", done
    archive = client.get(f"{API}/jobs/{job['id']}/download").content
    unpacked = tmp_path / "out"  # a folder the server may read from
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        zf.extractall(unpacked)
    row = json.loads((unpacked / "metadata.jsonl").read_text(encoding="utf-8"))
    assert row["texts"] == ["A stop sign on a corner.", "Second caption."]
    assert row["text"] == "A stop sign on a corner."
    assert row["split"] == "test"
    assert row["regions"][0]["text"] == "STOP"

    # Into a fresh project with the same picture, the text and the region come back.
    other = client.post(
        f"{API}/projects", json={"name": "Copy", "annotation_types": ["box", "text"]}
    ).json()
    picture = tmp_path / "a.png"
    PILImage.new("RGB", (40, 20), "white").save(picture)
    copy_id = client.post(
        f"{API}/projects/{other['id']}/images",
        files={"file": ("a.png", picture.read_bytes(), "image/png")},
    ).json()["id"]
    imported = client.post(
        f"{API}/projects/{other['id']}/imports", json={"path": str(unpacked)}
    ).json()
    result = wait_job(client, imported["id"])
    assert result["status"] == "done", result
    back = client.get(f"{API}/images/{copy_id}/annotations").json()
    kinds = sorted(a["type"] for a in back)
    assert kinds == ["box", "text", "text"]
    box_back = next(a for a in back if a["type"] == "box")
    assert box_back["attrs"] == {"transcription": "STOP"}


def test_other_formats_leave_text_out(client: TestClient, image: tuple[str, str]) -> None:
    project, image_id = image
    sign = client.post(f"{API}/projects/{project}/classes", json={"name": "sign"}).json()
    box = {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}
    send(
        client,
        image_id,
        make("text", {"text": "A stop sign."}),
        make("box", box, class_id=sign["id"]),
    )
    job = client.post(f"{API}/projects/{project}/exports", json={"format": "yolo-detect"}).json()
    done = wait_job(client, job["id"])
    assert done["status"] == "done", done
    assert done["result"]["shapes"] == 1
