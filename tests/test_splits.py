import io
import time
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


def upload(api: TestClient, project: str, index: int) -> str:
    buffer = io.BytesIO()
    PILImage.new("RGB", (8, 8), (index * 7 % 256, index * 13 % 256, index * 29 % 256)).save(
        buffer, "PNG"
    )
    buffer.seek(0)
    reply = api.post(
        f"{API}/projects/{project}/images", files={"file": (f"p{index}.png", buffer, "image/png")}
    )
    assert reply.status_code == 201, reply.text
    return str(reply.json()["id"])


def wait_job(api: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(300):
        job: dict[str, Any] = api.get(f"{API}/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


@pytest.fixture
def api(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(storage={"data_dir": str(tmp_path / "data")}))) as c:
        yield c


@pytest.fixture
def project(api: TestClient) -> str:
    made = api.post(f"{API}/projects", json={"name": "Cars", "annotation_types": ["box"]}).json()[
        "id"
    ]
    for i in range(10):
        upload(api, made, i)
    return str(made)


def state(api: TestClient, project: str) -> dict[str, object]:
    return dict(api.get(f"{API}/projects/{project}/splits").json())


def test_a_new_project_starts_with_ratios_for_its_kind(api: TestClient, project: str) -> None:
    got = state(api, project)
    assert got["kind"] == "detect"
    assert got["ratios"] == {"train": 0.8, "val": 0.1, "test": 0.1}
    assert got["counts"] == {"train": 0, "val": 0, "test": 0, "none": 10}


def test_a_preview_changes_nothing(api: TestClient, project: str) -> None:
    body = {"ratios": {"train": 0.6, "val": 0.2, "test": 0.2}, "seed": 3, "dry_run": True}
    got = api.post(f"{API}/projects/{project}/splits:shuffle", json=body).json()
    assert got["counts"] == {"train": 6, "val": 2, "test": 2}
    assert state(api, project)["counts"]["none"] == 10  # type: ignore[index]


def test_shuffle_saves_the_split_and_undo_takes_it_back(api: TestClient, project: str) -> None:
    body = {"ratios": {"train": 0.6, "val": 0.2, "test": 0.2}, "seed": 3}
    done = api.post(f"{API}/projects/{project}/splits:shuffle", json=body).json()
    assert state(api, project)["counts"] == {"train": 6, "val": 2, "test": 2, "none": 0}
    assert state(api, project)["ratios"] == {"train": 0.6, "val": 0.2, "test": 0.2}

    again = api.post(f"{API}/projects/{project}/splits:shuffle", json=body).json()
    assert again["moved"] == 0  # same seed, same result

    undo = api.post(f"{API}/operations/{done['operation']['id']}:revert")
    assert undo.status_code == 200
    assert state(api, project)["counts"]["none"] == 10  # type: ignore[index]


def test_a_new_seed_reshuffles(api: TestClient, project: str) -> None:
    first = {"ratios": {"train": 0.5, "val": 0.5}, "seed": 1}
    api.post(f"{API}/projects/{project}/splits:shuffle", json=first)
    before = {
        i["filename"]: i["split"]
        for i in api.get(f"{API}/projects/{project}/images").json()["items"]
    }
    api.post(f"{API}/projects/{project}/splits:shuffle", json={**first, "seed": 2})
    after = {
        i["filename"]: i["split"]
        for i in api.get(f"{API}/projects/{project}/images").json()["items"]
    }
    assert before != after


def test_only_unassigned_images_are_filled_in(api: TestClient, project: str) -> None:
    ids = [i["id"] for i in api.get(f"{API}/projects/{project}/images").json()["items"]]
    api.post(
        f"{API}/projects/{project}/images:assign-split",
        json={"image_ids": ids[:4], "split": "test"},
    )
    body = {"ratios": {"train": 1}, "only_unassigned": True}
    api.post(f"{API}/projects/{project}/splits:shuffle", json=body)
    assert state(api, project)["counts"] == {"train": 6, "val": 0, "test": 4, "none": 0}


def test_images_can_be_moved_by_hand_and_filtered(api: TestClient, project: str) -> None:
    ids = [i["id"] for i in api.get(f"{API}/projects/{project}/images").json()["items"]]
    moved = api.post(
        f"{API}/projects/{project}/images:assign-split", json={"image_ids": ids[:3], "split": "val"}
    ).json()
    assert moved == {"changed": 3}
    val = api.get(f"{API}/projects/{project}/images", params={"split": "val"}).json()["items"]
    none = api.get(f"{API}/projects/{project}/images", params={"split": "none"}).json()["items"]
    assert len(val) == 3 and len(none) == 7


def test_bad_ratios_are_refused(api: TestClient, project: str) -> None:
    for ratios in ({"train": 0}, {"train": -1, "val": 2}, {"holdout": 1}):
        reply = api.post(f"{API}/projects/{project}/splits:shuffle", json={"ratios": ratios})
        assert reply.status_code == 422 or reply.status_code == 400, ratios


def test_export_uses_the_saved_split(api: TestClient, project: str, tmp_path: Path) -> None:
    api.post(f"{API}/projects/{project}/classes", json={"name": "car"})
    body = {"ratios": {"train": 0.5, "test": 0.5}}
    api.post(f"{API}/projects/{project}/splits:shuffle", json=body)
    job = api.post(f"{API}/projects/{project}/exports", json={"format": "yolo-detect"}).json()
    done = wait_job(api, job["id"])
    assert done["status"] == "done", done
    archive = api.get(f"{API}/jobs/{job['id']}/download").content
    names = zipfile.ZipFile(io.BytesIO(archive)).namelist()
    assert any(n.startswith("labels/train/") for n in names)
    assert any(n.startswith("labels/test/") for n in names)
    assert not any(n.startswith("labels/val/") for n in names)
