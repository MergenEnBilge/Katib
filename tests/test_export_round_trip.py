"""Every export format, out through the API and back in again.

The format modules have their own tests. This checks the whole path a person actually takes:
export a project to a zip, unpack it, import it into an empty project, and see that the shapes
came back. It is the test that catches a zip with the wrong layout, an exporter that drops a
shape kind without saying so, and an importer that cannot read what the exporter just wrote.
"""

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

#: One of each kind Katib can draw, so a format that quietly drops one is caught.
SHAPES: list[tuple[str, dict[str, Any]]] = [
    ("box", {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}),
    ("polygon", {"points": [[0.5, 0.5], [0.8, 0.5], [0.8, 0.9], [0.5, 0.9]]}),
    ("obb", {"cx": 0.5, "cy": 0.3, "w": 0.2, "h": 0.1, "angle": 0.4}),
    (
        "keypoints",
        {"points": [{"x": 0.2, "y": 0.2, "v": 2}, {"x": 0.3, "y": 0.4, "v": 2}]},
    ),
]

#: What each format is meant to keep. A format is not broken for writing a polygon as a box, but
#: it is broken if a shape it claims to support disappears.
KEEPS: dict[str, set[str]] = {
    "yolo-detect": {"box"},
    "yolo-segment": {"polygon"},
    "yolo-obb": {"obb"},
    "coco": {"box", "polygon", "keypoints"},
    "voc": {"box"},
    "labelme": {"box", "polygon"},
}


@pytest.fixture
def api(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        storage={"data_dir": str(tmp_path / "data"), "allowed_import_roots": [str(tmp_path)]}
    )
    with TestClient(create_app(settings)) as client:
        yield client


def wait(api: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(400):
        job: dict[str, Any] = api.get(f"{API}/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def make_project(api: TestClient, tmp_path: Path, name: str) -> str:
    project = api.post(
        f"{API}/projects",
        json={"name": name, "annotation_types": ["box", "polygon", "obb", "keypoints"]},
    ).json()["id"]
    picture = tmp_path / f"{name}.png"
    PILImage.new("RGB", (800, 400), "gray").save(picture)
    api.post(
        f"{API}/projects/{project}/images",
        files={"file": ("photo.png", picture.read_bytes(), "image/png")},
    )
    return str(project)


def draw(api: TestClient, image: str, ops: list[dict[str, Any]]) -> None:
    made = api.post(f"{API}/images/{image}/annotations:batch", json={"ops": ops})
    assert made.status_code == 200, made.text
    for result in made.json()["results"]:
        assert result["status"] == "ok", result


def fill(api: TestClient, project: str) -> None:
    api.post(f"{API}/projects/{project}/classes", json={"name": "car", "keypoints": ["a", "b"]})
    image = api.get(f"{API}/projects/{project}/images").json()["items"][0]["id"]
    cls = api.get(f"{API}/projects/{project}/classes").json()[0]["id"]
    draw(
        api,
        image,
        [
            {
                "op": "create",
                "id": str(uuid.uuid4()),
                "class_id": cls,
                "type": kind,
                "geometry": geometry,
            }
            for kind, geometry in SHAPES
        ],
    )


def export_to(api: TestClient, project: str, fmt: str, into: Path) -> dict[str, Any]:
    started = api.post(
        f"{API}/projects/{project}/exports", json={"format": fmt, "copy_images": True}
    )
    assert started.status_code == 202, started.text
    job = wait(api, started.json()["id"])
    assert job["status"] == "done", job
    body = api.get(f"{API}/jobs/{job['id']}/download")
    assert body.status_code == 200, body.text
    archive = into.with_suffix(".zip")
    archive.write_bytes(body.content)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(into)
    result: dict[str, Any] = job["result"]
    return result


@pytest.mark.parametrize("fmt", sorted(KEEPS))
def test_a_project_survives_a_trip_out_and_back(api: TestClient, tmp_path: Path, fmt: str) -> None:
    source = make_project(api, tmp_path, "source")
    fill(api, source)
    folder = tmp_path / f"out-{fmt}"
    report = export_to(api, source, fmt, folder)
    assert report["images"] == 1
    assert report["shapes"] >= 1

    target = make_project(api, tmp_path, "target")
    started = api.post(
        f"{API}/projects/{target}/imports", json={"path": str(folder), "format": fmt}
    )
    assert started.status_code == 202, started.text
    job = wait(api, started.json()["id"])
    assert job["status"] == "done", job
    assert job["result"]["images_matched"] == 1

    image = api.get(f"{API}/projects/{target}/images").json()["items"][0]["id"]
    kinds = {a["type"] for a in api.get(f"{API}/images/{image}/annotations").json()}
    assert KEEPS[fmt] <= kinds, f"{fmt} lost {KEEPS[fmt] - kinds}"
    names = {c["name"] for c in api.get(f"{API}/projects/{target}/classes").json()}
    assert "car" in names


@pytest.mark.parametrize("fmt", sorted(KEEPS))
def test_an_export_carries_the_pictures(api: TestClient, tmp_path: Path, fmt: str) -> None:
    project = make_project(api, tmp_path, "pictures")
    fill(api, project)
    folder = tmp_path / f"images-{fmt}"
    export_to(api, project, fmt, folder)
    copied = [p for p in folder.rglob("*.png") if p.is_file()]
    assert copied, f"{fmt} exported no image files"
    assert copied[0].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_a_format_says_what_it_could_not_write(api: TestClient, tmp_path: Path) -> None:
    """Dropping a shape kind is fine. Dropping it without a word is not."""
    project = make_project(api, tmp_path, "notes")
    fill(api, project)
    report = export_to(api, project, "voc", tmp_path / "out-notes")
    reasons = " ".join(n["reason"] for n in report["notes"])
    assert "keypoints" in reasons.lower()


def test_text_goes_out_as_lines_and_comes_back(api: TestClient, tmp_path: Path) -> None:
    project = api.post(
        f"{API}/projects", json={"name": "captions", "annotation_types": ["text"]}
    ).json()["id"]
    picture = tmp_path / "c.png"
    PILImage.new("RGB", (400, 200), "gray").save(picture)
    api.post(
        f"{API}/projects/{project}/images",
        files={"file": ("photo.png", picture.read_bytes(), "image/png")},
    )
    image = api.get(f"{API}/projects/{project}/images").json()["items"][0]["id"]
    draw(
        api,
        image,
        [
            {
                "op": "create",
                "id": str(uuid.uuid4()),
                "type": "text",
                "geometry": {"text": "a gray square"},
            }
        ],
    )

    folder = tmp_path / "out-text"
    export_to(api, project, "jsonl", folder)
    written = list(folder.rglob("*.jsonl"))
    assert written, "no jsonl file was written"
    assert "a gray square" in written[0].read_text(encoding="utf-8")
