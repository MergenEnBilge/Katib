import time
from pathlib import Path
from typing import Any

import numpy as np
import onnx
import pytest
from fastapi.testclient import TestClient
from onnx import TensorProto, helper, numpy_helper
from PIL import Image as PILImage

from katib.api.app import create_app
from katib.config import Settings
from katib.ml import onnx as ml

API = "/api/v1"

# Three candidates for a two class model, in YOLOv8 layout (4 box values then a score per class).
# The picture is 800 by 400 and the model input 640, so the picture is padded 160 px top and bottom.
CANDIDATES = np.array(
    [
        [320, 322, 60],  # cx
        [320, 321, 60],  # cy
        [160, 160, 20],  # w
        [80, 80, 20],  # h
        [0.9, 0.6, 0.1],  # car score
        [0.05, 0.05, 0.1],  # bus score
    ],
    dtype=np.float32,
)


def write_model(path: Path, names: str | None = "{0: 'car', 1: 'bus'}") -> None:
    """A model that ignores its input and always answers with CANDIDATES."""
    output = helper.make_tensor_value_info("output0", TensorProto.FLOAT, [1, 6, 3])
    source = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, 640, 640])
    fixed = numpy_helper.from_array(CANDIDATES[None], name="fixed")
    node = helper.make_node("Constant", [], ["output0"], value=fixed)
    graph = helper.make_graph([node], "fixed", [source], [output])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    if names:
        entry = model.metadata_props.add()
        entry.key, entry.value = "names", names
    onnx.save(model, str(path))


@pytest.fixture
def models(tmp_path: Path) -> Path:
    folder = tmp_path / "models"
    folder.mkdir()
    write_model(folder / "cars.onnx")
    return folder


def test_the_detector_reads_names_and_finds_the_car(models: Path, tmp_path: Path) -> None:
    detector = ml.OnnxDetector(models / "cars.onnx")
    assert detector.class_names == ["car", "bus"]
    picture = tmp_path / "a.png"
    PILImage.new("RGB", (800, 400), "gray").save(picture)

    found = detector.detect(picture, threshold=0.5)

    # The two overlapping car candidates collapse to the stronger one. The weak third is dropped.
    assert [(d.class_index, round(d.score, 2)) for d in found] == [(0, 0.9)]
    assert (found[0].x, found[0].y, found[0].w, found[0].h) == pytest.approx(
        (0.375, 0.375, 0.25, 0.25), abs=0.01
    )


def test_a_file_that_is_not_a_model_is_refused_plainly(tmp_path: Path) -> None:
    bad = tmp_path / "bad.onnx"
    bad.write_text("not a model")
    with pytest.raises(ml.ModelError, match="bad.onnx could not be loaded"):
        ml.OnnxDetector(bad)


def test_only_onnx_files_are_listed(models: Path) -> None:
    (models / "notes.txt").write_text("hi")
    assert ml.list_models(models) == ["cars.onnx"]
    assert ml.list_models(models / "missing") == []


def wait_job(api: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(400):
        job = api.get(f"{API}/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


@pytest.fixture
def api(tmp_path: Path, models: Path) -> Any:
    settings = Settings(
        storage={"data_dir": str(tmp_path / "data")},
        ml={"enabled": True, "models_dir": str(models)},
    )
    with TestClient(create_app(settings)) as client:
        yield client


def project_with_images(api: TestClient, tmp_path: Path, count: int = 2) -> str:
    project = api.post(f"{API}/projects", json={"name": "Cars"}).json()
    for i in range(count):
        picture = tmp_path / f"p{i}.png"
        PILImage.new("RGB", (800, 400), (i * 40, 90, 90)).save(picture)
        api.post(
            f"{API}/projects/{project['id']}/images",
            files={"file": (picture.name, picture.read_bytes(), "image/png")},
        )
    return str(project["id"])


def test_status_lists_models_with_their_class_names(api: TestClient) -> None:
    body = api.get(f"{API}/ml").json()
    assert body["enabled"] is True and body["installed"] is True
    assert body["models"] == [{"name": "cars.onnx", "classes": ["car", "bus"]}]


def test_prelabel_saves_model_boxes_and_can_be_undone(api: TestClient, tmp_path: Path) -> None:
    project = project_with_images(api, tmp_path)
    started = api.post(
        f"{API}/projects/{project}/prelabel", json={"model": "cars.onnx", "threshold": 0.5}
    )
    assert started.status_code == 202, started.text
    job = wait_job(api, started.json()["id"])

    assert job["status"] == "done", job
    assert job["result"]["shapes"] == 2 and job["result"]["images"] == 2
    classes = {
        c["name"]: c["annotation_count"]
        for c in api.get(f"{API}/projects/{project}/classes").json()
    }
    assert classes == {"car": 2, "bus": 0}
    images = api.get(f"{API}/projects/{project}/images").json()["items"]
    shape = api.get(f"{API}/images/{images[0]['id']}/annotations").json()[0]
    assert shape["source"] == "model" and shape["confidence"] == pytest.approx(0.9)

    undone = api.post(f"{API}/operations/{job['result']['operation_id']}:revert")
    assert undone.status_code == 200
    assert undone.json()["restored"] == 2
    assert api.get(f"{API}/images/{images[0]['id']}/annotations").json() == []


def test_only_unlabeled_images_are_touched_by_default(api: TestClient, tmp_path: Path) -> None:
    project = project_with_images(api, tmp_path)
    first = api.get(f"{API}/projects/{project}/images").json()["items"][0]["id"]
    car = api.post(f"{API}/projects/{project}/classes", json={"name": "car"}).json()["id"]
    api.post(
        f"{API}/images/{first}/annotations:batch",
        json={
            "ops": [
                {
                    "op": "create",
                    "id": "0192d000-0000-7000-8000-000000000001",
                    "type": "box",
                    "class_id": car,
                    "geometry": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
                }
            ]
        },
    )

    job = wait_job(
        api,
        api.post(
            f"{API}/projects/{project}/prelabel", json={"model": "cars.onnx", "threshold": 0.5}
        ).json()["id"],
    )
    assert job["result"]["images"] == 1
    assert len(api.get(f"{API}/images/{first}/annotations").json()) == 1


def test_classes_can_be_left_out_instead_of_created(api: TestClient, tmp_path: Path) -> None:
    project = project_with_images(api, tmp_path, count=1)
    body = {"model": "cars.onnx", "threshold": 0.5, "create_missing_classes": False}
    job = wait_job(api, api.post(f"{API}/projects/{project}/prelabel", json=body).json()["id"])
    assert job["result"]["shapes"] == 0
    assert job["result"]["skipped_classes"] == ["car", "bus"]


def test_a_model_outside_the_folder_is_not_found(api: TestClient, tmp_path: Path) -> None:
    project = project_with_images(api, tmp_path, count=1)
    res = api.post(f"{API}/projects/{project}/prelabel", json={"model": "../secret.onnx"})
    assert res.status_code == 404


def test_a_model_can_be_added_from_the_browser(api: TestClient, tmp_path: Path) -> None:
    """In Docker the models folder is inside the container, so copying a file there is not an
    option. Uploading is the only way in."""
    source = tmp_path / "vans.onnx"
    write_model(source, names="{0: 'van'}")
    added = api.post(
        f"{API}/ml/models", files={"file": ("vans.onnx", source.read_bytes(), "application/onnx")}
    )
    assert added.status_code == 201, added.text
    assert added.json()["name"] == "vans.onnx"
    assert [m["name"] for m in api.get(f"{API}/ml").json()["models"]] == ["cars.onnx", "vans.onnx"]


def test_only_onnx_files_can_be_uploaded(api: TestClient) -> None:
    refused = api.post(f"{API}/ml/models", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert refused.status_code == 422
    assert ".onnx" in refused.json()["message"]


def test_an_uploaded_model_cannot_escape_the_models_folder(api: TestClient, tmp_path: Path) -> None:
    source = tmp_path / "escape.onnx"
    write_model(source)
    sent = api.post(
        f"{API}/ml/models",
        files={"file": ("../../escape.onnx", source.read_bytes(), "application/onnx")},
    )
    assert sent.status_code == 201
    assert sent.json()["name"] == "escape.onnx"
    assert not (tmp_path.parent / "escape.onnx").exists()


def test_a_model_that_is_already_there_is_not_overwritten(api: TestClient, tmp_path: Path) -> None:
    source = tmp_path / "cars.onnx"
    write_model(source)
    refused = api.post(
        f"{API}/ml/models", files={"file": ("cars.onnx", source.read_bytes(), "application/onnx")}
    )
    assert refused.status_code == 422
    assert "already a model" in refused.json()["message"]


def test_it_says_how_to_turn_it_on_when_it_is_off(tmp_path: Path) -> None:
    with TestClient(create_app(Settings(storage={"data_dir": str(tmp_path)}))) as client:
        project = client.post(f"{API}/projects", json={"name": "P"}).json()["id"]
        res = client.post(f"{API}/projects/{project}/prelabel", json={"model": "x.onnx"})
    assert res.status_code == 403
    # The message points at the switch in Settings, not at the setting's name in a file.
    assert "Settings" in res.json()["message"]
