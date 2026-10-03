"""Connecting a folder that is already a labelled dataset.

Katib's own "Import labels" step already reads YOLO, COCO, VOC and LabelMe, matches by filename,
and picks the split out of the folder layout. Connecting a folder should not make someone repeat
that by hand: when the folder it points at already looks like one of those formats, the same
classes, splits and shapes come along with the pictures, in one step. A folder with nothing but
photos in it must behave exactly as before — this only ever adds to that, never replaces it.
"""

import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from PIL import Image as PILImage

from katib.api.app import create_app
from katib.config import Settings

API = "/api/v1"


def photo(path: Path, size: tuple[int, int] = (16, 16), color: str = "gray") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    PILImage.new("RGB", size, color).save(path)


def wait_job(api: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(400):
        job = api.get(f"{API}/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


@pytest.fixture
def solo(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(storage={"data_dir": str(tmp_path / "data")}))) as c:
        yield c


def connect(api: TestClient, project: str, folder: Path) -> dict[str, Any]:
    made = api.post(f"{API}/projects/{project}/folders", json={"path": str(folder)}).json()
    return wait_job(api, made["job"]["id"])


def test_connecting_a_yolo_folder_reads_classes_splits_and_boxes(
    solo: TestClient, tmp_path: Path
) -> None:
    lib = tmp_path / "yolo-set"
    # Labels are organized by split; the pictures sit flat in one folder, so only the label side
    # of the auto-import can know which split each one belongs to.
    (lib / "labels" / "train").mkdir(parents=True)
    (lib / "labels" / "val").mkdir(parents=True)
    (lib / "labels" / "train" / "a.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    (lib / "labels" / "val" / "b.txt").write_text("1 0.5 0.5 0.3 0.3\n", encoding="utf-8")
    (lib / "data.yaml").write_text(
        yaml.safe_dump(
            {"path": ".", "train": "images", "val": "images", "names": {0: "car", 1: "bus"}}
        ),
        encoding="utf-8",
    )
    photo(lib / "images" / "a.png", color="red")
    photo(lib / "images" / "b.png", color="blue")

    project = solo.post(f"{API}/projects", json={"name": "Cars"}).json()["id"]
    job = connect(solo, project, lib)

    assert job["status"] == "done", job
    assert job["result"]["added"] == 2
    dataset = job["result"]["dataset"]
    assert dataset["format"] == "yolo-detect"
    assert dataset["shapes_added"] == 2
    assert sorted(dataset["classes_created"]) == ["bus", "car"]
    assert dataset["splits_set"] == 2

    classes = {c["name"] for c in solo.get(f"{API}/projects/{project}/classes").json()}
    assert classes == {"car", "bus"}
    images = solo.get(f"{API}/projects/{project}/images").json()["items"]
    splits = {i["filename"]: i["split"] for i in images}
    assert splits == {"a.png": "train", "b.png": "val"}
    shapes = {i["filename"]: solo.get(f"{API}/images/{i['id']}/annotations").json() for i in images}
    assert all(len(s) == 1 and s[0]["type"] == "box" for s in shapes.values())


def test_connecting_a_coco_folder_reads_classes_and_boxes(solo: TestClient, tmp_path: Path) -> None:
    lib = tmp_path / "coco-set"
    lib.mkdir()
    photo(lib / "photo.png", size=(100, 80))
    coco = {
        "images": [{"id": 1, "file_name": "photo.png", "width": 100, "height": 80}],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 1, "bbox": [10, 10, 20, 20], "iscrowd": 0}
        ],
        "categories": [{"id": 1, "name": "sign"}],
    }
    (lib / "annotations.json").write_text(json.dumps(coco), encoding="utf-8")

    project = solo.post(f"{API}/projects", json={"name": "Signs"}).json()["id"]
    job = connect(solo, project, lib)

    assert job["status"] == "done", job
    dataset = job["result"]["dataset"]
    assert dataset["format"] == "coco"
    assert dataset["shapes_added"] == 1
    assert dataset["classes_created"] == ["sign"]

    image = solo.get(f"{API}/projects/{project}/images").json()["items"][0]
    shapes = solo.get(f"{API}/images/{image['id']}/annotations").json()
    assert len(shapes) == 1 and shapes[0]["type"] == "box"


def test_a_plain_folder_of_photos_gets_no_dataset(solo: TestClient, tmp_path: Path) -> None:
    """The common case: nothing recognizable, so nothing beyond the pictures happens."""
    lib = tmp_path / "just-photos"
    photo(lib / "a.png", color="red")
    photo(lib / "b.png", color="blue")

    project = solo.post(f"{API}/projects", json={"name": "P"}).json()["id"]
    job = connect(solo, project, lib)

    assert job["status"] == "done", job
    assert job["result"]["added"] == 2
    assert job["result"]["dataset"]["state"] == "none"
    assert solo.get(f"{API}/projects/{project}/classes").json() == []


def test_rescanning_a_connected_folder_also_catches_up_on_labels(
    solo: TestClient, tmp_path: Path
) -> None:
    """A folder connected before it had labels should not need a separate re-import step
    once the labels turn up next to the pictures it already knows about."""
    lib = tmp_path / "grows"
    photo(lib / "a.png")
    project = solo.post(f"{API}/projects", json={"name": "P"}).json()["id"]
    first = connect(solo, project, lib)
    assert first["result"]["dataset"]["state"] == "none"

    (lib / "data.yaml").write_text(
        yaml.safe_dump({"path": ".", "train": "images", "val": "images", "names": {0: "car"}}),
        encoding="utf-8",
    )
    (lib / "labels" / "a.txt").parent.mkdir(parents=True, exist_ok=True)
    (lib / "labels" / "a.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")

    folder_id = solo.get(f"{API}/projects/{project}/folders").json()[0]["id"]
    rescan = wait_job(
        solo, solo.post(f"{API}/projects/{project}/folders/{folder_id}:rescan").json()["id"]
    )
    assert rescan["status"] == "done", rescan
    assert rescan["result"]["dataset"]["shapes_added"] == 1

    image = solo.get(f"{API}/projects/{project}/images").json()["items"][0]
    shapes = solo.get(f"{API}/images/{image['id']}/annotations").json()
    assert len(shapes) == 1
