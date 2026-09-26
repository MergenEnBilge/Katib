"""Click to select, with a stand-in for Segment Anything.

The real model is three hundred megabytes of weights nobody should download to run a test. What
matters here is the plumbing around it: the picture reaching the encoder in the shape it expects,
the clicks reaching the decoder, and the mask coming back as an outline. Two tiny ONNX files that
answer with fixed values exercise all of that.
"""

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
from katib.ml import sam

API = "/api/v1"

#: The shape of the stand-in embedding. The real one is 1x256x64x64, which is four megabytes.
EMBEDDING = [1, 1, 2, 2]

#: A 40 by 40 mask with a square from 10 to 30. Positive values are inside the object.
MASK_SIDE = 40


def constant_model(path: Path, inputs: list[Any], name: str, value: np.ndarray) -> None:
    output = helper.make_tensor_value_info(name, TensorProto.FLOAT, list(value.shape))
    node = helper.make_node("Constant", [], [name], value=numpy_helper.from_array(value, "fixed"))
    graph = helper.make_graph([node], "fixed", inputs, [output])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    onnx.save(model, str(path))


def write_encoder(path: Path) -> None:
    source = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, 1024, 1024])
    constant_model(path, [source], "embedding", np.zeros(EMBEDDING, dtype=np.float32))


def write_decoder(path: Path) -> None:
    grid = np.full((MASK_SIDE, MASK_SIDE), -1.0, dtype=np.float32)
    grid[10:30, 10:30] = 1.0
    inputs = [
        helper.make_tensor_value_info("image_embeddings", TensorProto.FLOAT, EMBEDDING),
        helper.make_tensor_value_info("point_coords", TensorProto.FLOAT, [1, None, 2]),
        helper.make_tensor_value_info("point_labels", TensorProto.FLOAT, [1, None]),
        helper.make_tensor_value_info("mask_input", TensorProto.FLOAT, [1, 1, 256, 256]),
        helper.make_tensor_value_info("has_mask_input", TensorProto.FLOAT, [1]),
        helper.make_tensor_value_info("orig_im_size", TensorProto.FLOAT, [2]),
    ]
    constant_model(path, inputs, "masks", grid[None, None])


@pytest.fixture
def models(tmp_path: Path) -> Path:
    folder = tmp_path / "models"
    folder.mkdir()
    write_encoder(folder / sam.ENCODER_NAME)
    write_decoder(folder / sam.DECODER_NAME)
    return folder


@pytest.fixture
def api(tmp_path: Path, models: Path) -> Any:
    settings = Settings(
        storage={"data_dir": str(tmp_path / "data")},
        ml={"enabled": True, "models_dir": str(models)},
    )
    with TestClient(create_app(settings)) as client:
        yield client


def project_with_image(api: TestClient, tmp_path: Path) -> tuple[str, str]:
    project = api.post(f"{API}/projects", json={"name": "Things"}).json()["id"]
    picture = tmp_path / "a.png"
    PILImage.new("RGB", (800, 400), "gray").save(picture)
    made = api.post(
        f"{API}/projects/{project}/images",
        files={"file": (picture.name, picture.read_bytes(), "image/png")},
    ).json()
    return str(project), str(made["images"][0]["id"] if "images" in made else made["id"])


def test_a_click_comes_back_as_an_outline(api: TestClient, tmp_path: Path) -> None:
    project, image = project_with_image(api, tmp_path)
    reply = api.post(
        f"{API}/projects/{project}/images/{image}/segment",
        json={"points": [{"x": 0.5, "y": 0.5, "positive": True}]},
    )
    assert reply.status_code == 200, reply.text
    points = reply.json()["points"]
    assert len(points) >= 4
    # The stand-in marks the middle of the picture, so the outline has to sit there too.
    assert all(0.2 < x < 0.8 and 0.2 < y < 0.8 for x, y in points)


def test_the_model_is_told_where_the_click_was(models: Path, tmp_path: Path) -> None:
    """Whatever the mask says, the clicks have to arrive in the space the decoder works in."""
    picture = tmp_path / "a.png"
    PILImage.new("RGB", (800, 400), "gray").save(picture)
    segmenter = sam.SamSegmenter(models)
    seen: list[Any] = []
    real = segmenter._decoder.run

    def spy(names: Any, feed: Any) -> Any:
        seen.append(feed)
        return real(names, feed)

    segmenter._decoder.run = spy  # type: ignore[method-assign]
    segmenter.outline(picture, "one", [sam.Click(x=0.5, y=0.25)])

    coords = seen[0]["point_coords"][0]
    assert len(coords) == 2  # the click, plus the padding point SAM expects
    # The picture is twice as wide as it is tall, so 1024 across and 512 down.
    assert coords[0] == pytest.approx([512.0, 128.0], abs=1.0)
    assert seen[0]["point_labels"][0].tolist() == [1.0, -1.0]


def test_the_picture_is_only_looked_at_once(models: Path, tmp_path: Path) -> None:
    """Encoding is the slow half. Clicking again on the same picture must not pay for it twice."""
    picture = tmp_path / "a.png"
    PILImage.new("RGB", (800, 400), "gray").save(picture)
    segmenter = sam.SamSegmenter(models)
    runs = 0
    real = segmenter._encoder.run

    def count(names: Any, feed: Any) -> Any:
        nonlocal runs
        runs += 1
        return real(names, feed)

    segmenter._encoder.run = count  # type: ignore[method-assign]
    for _ in range(3):
        segmenter.outline(picture, "one", [sam.Click(x=0.5, y=0.5)])
    assert runs == 1


def test_clicking_without_a_model_says_what_is_missing(tmp_path: Path) -> None:
    settings = Settings(
        storage={"data_dir": str(tmp_path / "data")},
        ml={"enabled": True, "models_dir": str(tmp_path / "empty")},
    )
    with TestClient(create_app(settings)) as client:
        project, image = project_with_image(client, tmp_path)
        reply = client.post(
            f"{API}/projects/{project}/images/{image}/segment",
            json={"points": [{"x": 0.5, "y": 0.5}]},
        )
    assert reply.status_code == 422
    assert "Segment Anything" in reply.json()["message"]


def test_clicking_with_model_help_off_is_refused(tmp_path: Path, models: Path) -> None:
    settings = Settings(
        storage={"data_dir": str(tmp_path / "data")}, ml={"models_dir": str(models)}
    )
    with TestClient(create_app(settings)) as client:
        project, image = project_with_image(client, tmp_path)
        reply = client.post(
            f"{API}/projects/{project}/images/{image}/segment",
            json={"points": [{"x": 0.5, "y": 0.5}]},
        )
    assert reply.status_code == 403


def test_the_status_says_whether_clicking_will_work(api: TestClient, tmp_path: Path) -> None:
    assert api.get(f"{API}/ml").json()["can_segment"] is True
