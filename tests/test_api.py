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
BOX = {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}


@pytest.fixture
def library(tmp_path: Path) -> Path:
    lib = tmp_path / "library"
    lib.mkdir()
    for i, color in enumerate(["red", "green", "blue"]):
        PILImage.new("RGB", (60 + i, 40), color).save(lib / f"img{i}.png")
    return lib


@pytest.fixture
def api(tmp_path: Path, library: Path) -> Iterator[TestClient]:
    settings = Settings(
        storage={"data_dir": str(tmp_path / "data"), "allowed_import_roots": [str(library)]}
    )
    with TestClient(create_app(settings)) as c:
        yield c


def make_project(api: TestClient, name: str = "Street") -> dict[str, Any]:
    res = api.post(f"{API}/projects", json={"name": name})
    assert res.status_code == 201, res.text
    return res.json()


def wait_job(api: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(300):
        job = api.get(f"{API}/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def import_library(api: TestClient, project: dict[str, Any], library: Path) -> dict[str, Any]:
    res = api.post(
        f"{API}/projects/{project['id']}/images:import-folder", json={"folder": str(library)}
    )
    assert res.status_code == 202, res.text
    return wait_job(api, res.json()["id"])


def test_project_lifecycle(api: TestClient) -> None:
    p = make_project(api)
    assert p["name"] == "Street" and p["image_count"] == 0
    assert [x["id"] for x in api.get(f"{API}/projects").json()] == [p["id"]]
    renamed = api.patch(f"{API}/projects/{p['id']}", json={"name": "Roads"}).json()
    assert renamed["name"] == "Roads"
    assert api.delete(f"{API}/projects/{p['id']}").status_code == 204
    assert api.get(f"{API}/projects/{p['id']}").status_code == 404


def test_error_shape(api: TestClient) -> None:
    make_project(api, "Dup")
    res = api.post(f"{API}/projects", json={"name": "dup"})
    assert res.status_code == 409
    body = res.json()
    assert body["code"] == "project_name_taken"
    assert "already exists" in body["message"]
    assert body["details"] == {}
    bad = api.post(f"{API}/projects", json={})
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_input"


def test_classes(api: TestClient) -> None:
    p = make_project(api)
    base = f"{API}/projects/{p['id']}/classes"
    car = api.post(base, json={"name": "car"}).json()
    bus = api.post(base, json={"name": "bus", "color": "#112233"}).json()
    assert (car["position"], bus["position"], bus["color"]) == (0, 1, "#112233")
    assert api.post(base, json={"name": "CAR"}).json()["code"] == "class_name_taken"
    renamed = api.patch(f"{API}/classes/{car['id']}", json={"name": "auto", "color": "#ffffff"})
    assert renamed.json()["name"] == "auto" and renamed.json()["color"] == "#FFFFFF"
    order = [bus["id"], car["id"]]
    assert api.post(f"{base}:reorder", json={"class_ids": order}).status_code == 204
    assert [c["id"] for c in api.get(base).json()] == order


def test_folder_import_list_and_serve(api: TestClient, library: Path) -> None:
    p = make_project(api)
    job = import_library(api, p, library)
    assert job["status"] == "done" and job["result"]["added"] == 3

    page = api.get(f"{API}/projects/{p['id']}/images", params={"limit": 2}).json()
    assert [i["filename"] for i in page["items"]] == ["img0.png", "img1.png"]
    rest = api.get(f"{API}/projects/{p['id']}/images", params={"after": page["next"]}).json()
    assert [i["filename"] for i in rest["items"]] == ["img2.png"]

    image_id = page["items"][0]["id"]
    original = api.get(f"{API}/images/{image_id}/file")
    assert original.status_code == 200
    assert original.content == (library / "img0.png").read_bytes()
    thumb = api.get(f"{API}/images/{image_id}/thumb")
    assert thumb.headers["content-type"] == "image/jpeg"
    assert api.get(f"{API}/projects/{p['id']}").json()["image_count"] == 3


def test_folder_outside_allowed_roots_is_403(api: TestClient, tmp_path: Path) -> None:
    p = make_project(api)
    res = api.post(f"{API}/projects/{p['id']}/images:import-folder", json={"folder": str(tmp_path)})
    assert res.status_code == 403
    assert res.json()["code"] == "import_not_allowed"


def test_upload(api: TestClient) -> None:
    p = make_project(api)
    buf = io.BytesIO()
    PILImage.new("RGB", (10, 10), "white").save(buf, "PNG")
    res = api.post(
        f"{API}/projects/{p['id']}/images",
        files={"file": ("shot.png", buf.getvalue(), "image/png")},
    )
    assert res.status_code == 201
    assert res.json()["filename"] == "shot.png"
    bad = api.post(
        f"{API}/projects/{p['id']}/images", files={"file": ("x.txt", b"hi", "text/plain")}
    )
    assert bad.status_code == 422


def test_annotation_batch_round_trip(api: TestClient, library: Path) -> None:
    p = make_project(api)
    car = api.post(f"{API}/projects/{p['id']}/classes", json={"name": "car"}).json()
    import_library(api, p, library)
    image = api.get(f"{API}/projects/{p['id']}/images").json()["items"][0]
    url = f"{API}/images/{image['id']}/annotations"

    ann_id = str(uuid.uuid4())
    create = {"op": "create", "id": ann_id, "type": "box", "class_id": car["id"], "geometry": BOX}
    res = api.post(f"{url}:batch", json={"ops": [create]}).json()
    assert res["results"][0]["status"] == "ok"
    assert res["results"][0]["annotation"]["version"] == 1

    api.post(f"{url}:batch", json={"ops": [create]})  # retry is harmless
    assert len(api.get(url).json()) == 1

    stale = {"op": "update", "id": ann_id, "if_version": 9, "patch": {"geometry": BOX}}
    conflict = api.post(f"{url}:batch", json={"ops": [stale]}).json()["results"][0]
    assert conflict["status"] == "conflict" and conflict["annotation"]["version"] == 1

    assert api.get(f"{API}/images/{image['id']}").json()["status"] == "in_progress"
    counts = api.get(f"{API}/projects/{p['id']}/classes").json()
    assert counts[0]["annotation_count"] == 1
    filtered = api.get(f"{API}/projects/{p['id']}/images", params={"class_id": car["id"]}).json()[
        "items"
    ]
    assert [i["id"] for i in filtered] == [image["id"]]


def test_mark_done(api: TestClient, library: Path) -> None:
    p = make_project(api)
    import_library(api, p, library)
    image = api.get(f"{API}/projects/{p['id']}/images").json()["items"][0]
    done = api.patch(f"{API}/images/{image['id']}", json={"status": "done"}).json()
    assert done["status"] == "done"
    assert api.get(f"{API}/projects/{p['id']}").json()["done_count"] == 1
    assert api.patch(f"{API}/images/{image['id']}", json={"status": "approved"}).status_code == 422


def test_formats_are_listed(api: TestClient) -> None:
    ids = {f["id"] for f in api.get(f"{API}/formats").json()}
    assert ids == {"yolo-detect", "coco"}


def test_yolo_import_then_coco_export(api: TestClient, library: Path, tmp_path: Path) -> None:
    p = make_project(api)
    import_library(api, p, library)
    (library / "labels").mkdir()
    (library / "data.yaml").write_text("names:\n  0: car\n  1: bus\n")
    (library / "labels" / "img0.txt").write_text("0 0.5 0.5 0.2 0.4\n1 0.2 0.2 0.1 0.1\n")

    res = api.post(f"{API}/projects/{p['id']}/imports", json={"path": str(library)})
    assert res.status_code == 202, res.text
    job = wait_job(api, res.json()["id"])
    assert job["status"] == "done", job
    assert job["result"]["format"] == "yolo-detect"
    assert job["result"]["shapes_added"] == 2
    assert job["result"]["classes_created"] == ["car", "bus"]

    again = wait_job(
        api, api.post(f"{API}/projects/{p['id']}/imports", json={"path": str(library)}).json()["id"]
    )
    assert again["result"]["shapes_added"] == 0
    assert "Already has shapes" in again["result"]["notes"][0]["reason"]

    counts = {
        c["name"]: c["annotation_count"]
        for c in api.get(f"{API}/projects/{p['id']}/classes").json()
    }
    assert counts == {"car": 1, "bus": 1}

    res = api.post(f"{API}/projects/{p['id']}/exports", json={"format": "coco"})
    assert res.status_code == 202, res.text
    job = wait_job(api, res.json()["id"])
    assert job["status"] == "done", job
    assert job["result"]["shapes"] == 2
    download = api.get(f"{API}/jobs/{job['id']}/download")
    assert download.status_code == 200
    with zipfile.ZipFile(io.BytesIO(download.content)) as z:
        doc = json.loads(z.read("annotations.json"))
    assert [c["name"] for c in doc["categories"]] == ["car", "bus"]
    assert len(doc["images"]) == 3 and len(doc["annotations"]) == 2


def test_import_path_outside_roots_and_empty_export(api: TestClient, tmp_path: Path) -> None:
    p = make_project(api)
    res = api.post(f"{API}/projects/{p['id']}/imports", json={"path": str(tmp_path)})
    assert res.status_code == 403
    res = api.post(f"{API}/projects/{p['id']}/exports", json={"format": "yolo-detect"})
    assert res.status_code == 422
    assert "no images" in res.json()["message"]
    assert api.get(f"{API}/jobs/{uuid.uuid4()}/download").status_code == 404
