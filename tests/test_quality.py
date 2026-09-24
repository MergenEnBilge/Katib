import io
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage

from katib.api.app import create_app
from katib.config import Settings

API = "/api/v1"


def solid(path: Path, color: str, size: tuple[int, int] = (80, 60)) -> None:
    PILImage.new("RGB", size, color).save(path)


@pytest.fixture
def api(tmp_path: Path) -> Iterator[TestClient]:
    lib = tmp_path / "lib"
    lib.mkdir()
    solid(lib / "a.png", "red")
    solid(lib / "b.png", "green")
    # A gradient differs in structure from the flat images, so its hash is far from theirs.
    gradient = PILImage.new("L", (80, 60))
    gradient.putdata([255 - x * 3 for _ in range(60) for x in range(80)])
    gradient.convert("RGB").save(lib / "c.png")
    settings = Settings(
        storage={"data_dir": str(tmp_path / "data"), "allowed_import_roots": [str(lib)]}
    )
    with TestClient(create_app(settings)) as c:
        c.headers["X-Lib"] = str(lib)
        yield c


def setup_project(api: TestClient) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    project = api.post(f"{API}/projects", json={"name": "Q"}).json()
    car = api.post(f"{API}/projects/{project['id']}/classes", json={"name": "car"}).json()
    job = api.post(
        f"{API}/projects/{project['id']}/images:import-folder",
        json={"folder": api.headers["X-Lib"]},
    ).json()
    for _ in range(200):
        if api.get(f"{API}/jobs/{job['id']}").json()["status"] == "done":
            break
    images = api.get(f"{API}/projects/{project['id']}/images").json()["items"]
    return project, car, images


def create(api: TestClient, image_id: str, class_id: str, geometry: dict[str, float]) -> str:
    ann_id = str(uuid.uuid4())
    api.post(
        f"{API}/images/{image_id}/annotations:batch",
        json={
            "ops": [
                {
                    "op": "create",
                    "id": ann_id,
                    "type": "box",
                    "class_id": class_id,
                    "geometry": geometry,
                }
            ]
        },
    )
    return ann_id


def test_health_report(api: TestClient) -> None:
    project, car, images = setup_project(api)
    first = images[0]["id"]
    create(api, first, car["id"], {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.3})
    create(api, first, car["id"], {"x": 0.101, "y": 0.1, "w": 0.3, "h": 0.3})
    tiny = create(api, first, car["id"], {"x": 0.5, "y": 0.5, "w": 0.004, "h": 0.2})

    report = api.get(f"{API}/projects/{project['id']}/health").json()
    assert report["images"] == 3 and report["annotations"] == 3
    assert report["empty_images"] == 2
    assert report["tiny_shapes"] == 1 and report["tiny_sample"] == [tiny]
    assert report["duplicate_shapes"] == 1
    assert report["class_counts"] == [{"name": "car", "count": 3}]
    assert report["imbalance"] is None
    # The two flat images have identical hashes, so they are reported as look-alikes.
    assert len(report["look_alikes"]) == 1 and len(report["look_alikes"][0]) == 2


def test_gallery_pages_and_filters(api: TestClient) -> None:
    project, car, images = setup_project(api)
    bus = api.post(f"{API}/projects/{project['id']}/classes", json={"name": "bus"}).json()
    ids = [
        create(api, images[0]["id"], car["id"], {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2})
        for _ in range(3)
    ]
    create(api, images[1]["id"], bus["id"], {"x": 0.2, "y": 0.2, "w": 0.2, "h": 0.2})
    url = f"{API}/projects/{project['id']}/shapes"

    first = api.get(url, params={"class_id": car["id"], "limit": 2}).json()
    assert len(first["items"]) == 2 and first["next"] is not None
    rest = api.get(url, params={"class_id": car["id"], "limit": 2, "after": first["next"]}).json()
    assert len(rest["items"]) == 1 and rest["next"] is None
    assert {i["id"] for i in first["items"] + rest["items"]} == set(ids)
    assert len(api.get(url, params={"class_id": bus["id"]}).json()["items"]) == 1
    assert api.get(url, params={"image_status": "done"}).json()["items"] == []


def test_gallery_tiny_filter(api: TestClient) -> None:
    project, car, images = setup_project(api)
    create(api, images[0]["id"], car["id"], {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.3})
    tiny = create(api, images[0]["id"], car["id"], {"x": 0.5, "y": 0.5, "w": 0.004, "h": 0.2})
    result = api.get(f"{API}/projects/{project['id']}/shapes", params={"tiny_only": True}).json()
    assert [i["id"] for i in result["items"]] == [tiny]


def test_crop_returns_a_small_jpeg(api: TestClient) -> None:
    _, car, images = setup_project(api)
    ann = create(api, images[0]["id"], car["id"], {"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5})
    res = api.get(f"{API}/annotations/{ann}/crop", params={"size": 64})
    assert res.status_code == 200 and res.headers["content-type"] == "image/jpeg"
    with PILImage.open(io.BytesIO(res.content)) as crop:
        assert max(crop.size) <= 64
    assert api.get(f"{API}/annotations/{uuid.uuid4()}/crop").status_code == 404
