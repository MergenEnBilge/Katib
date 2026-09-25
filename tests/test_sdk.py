import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from katib_client import Katib, KatibError
from PIL import Image as PILImage

from katib.api.app import create_app
from katib.config import Settings


def photo(path: Path, color: str = "red") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    PILImage.new("RGB", (40, 20), color).save(path)
    return path


@pytest.fixture
def library(tmp_path: Path) -> Path:
    lib = tmp_path / "library"
    photo(lib / "a.png", "red")
    photo(lib / "b.png", "blue")
    return lib


@pytest.fixture
def katib(tmp_path: Path) -> Iterator[Katib]:
    settings = Settings(storage={"data_dir": str(tmp_path / "data")})
    with TestClient(create_app(settings)) as app:
        yield Katib(http=app)


def test_a_script_can_make_a_project_label_an_image_and_export_it(
    katib: Katib, tmp_path: Path
) -> None:
    project = katib.projects.create("Street scenes")
    car = katib.classes.create(project.id, "car")
    image = katib.images.upload(project.id, photo(tmp_path / "one.png"))

    saved = katib.annotations.add_boxes(image.id, [(car.id, 0.1, 0.2, 0.3, 0.4)])

    assert saved == 1
    [shape] = katib.annotations.list(image.id)
    assert shape.type == "box" and shape.class_id == car.id
    assert shape.geometry == pytest.approx({"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4})

    exported = katib.export(project.id, "yolo-detect", tmp_path / "out")
    assert exported.suffix == ".zip"
    with zipfile.ZipFile(exported) as archive:
        assert "data.yaml" in archive.namelist()
        [label] = [n for n in archive.namelist() if n.endswith("one.txt")]
        assert archive.read(label).decode().startswith("0 0.250000 0.400000 0.300000 0.400000")


def test_images_can_be_listed_in_pages(katib: Katib, tmp_path: Path) -> None:
    project = katib.projects.create("Many")
    for i in range(5):
        katib.images.upload(project.id, photo(tmp_path / f"p{i}.png", (i * 40, 0, 0)))  # type: ignore[arg-type]
    names = [i.filename for i in katib.images.list(project.id, page_size=2)]
    assert sorted(names) == [f"p{i}.png" for i in range(5)]
    assert katib.projects.get(project.id).image_count == 5


def test_a_server_folder_can_be_connected(tmp_path: Path, library: Path) -> None:
    settings = Settings(storage={"data_dir": str(tmp_path / "data")})
    with TestClient(create_app(settings)) as app:
        katib = Katib(http=app)
        project = katib.projects.create("Folder")
        result = katib.images.connect_folder(project.id, library)
        assert result["added"] == 2
        assert {i.filename for i in katib.images.list(project.id)} == {"a.png", "b.png"}


def test_errors_carry_the_servers_code_and_message(katib: Katib) -> None:
    katib.projects.create("Same")
    with pytest.raises(KatibError) as caught:
        katib.projects.create("Same")
    assert caught.value.code == "project_name_taken"
    assert caught.value.status == 409
    assert "already exists" in caught.value.message


def test_a_refused_shape_raises_instead_of_failing_quietly(katib: Katib, tmp_path: Path) -> None:
    project = katib.projects.create("Boxes only")
    image = katib.images.upload(project.id, photo(tmp_path / "x.png"))
    with pytest.raises(KatibError, match="does not use tag"):
        katib.annotations.batch(
            image.id,
            [
                {
                    "op": "create",
                    "id": "0192d000-0000-7000-8000-000000000009",
                    "type": "tag",
                    "geometry": {},
                }
            ],
        )


def test_a_token_is_sent_when_given(tmp_path: Path) -> None:
    settings = Settings(storage={"data_dir": str(tmp_path / "data")}, auth={"mode": "local"})
    with TestClient(create_app(settings)) as app:
        app.post(
            "/api/v1/auth/setup",
            json={"email": "a@example.com", "name": "A", "password": "correct horse battery"},
        )
        token = app.post("/api/v1/auth/tokens", json={"name": "script"}).json()["token"]
        fresh = TestClient(app.app)
        with pytest.raises(KatibError) as caught:
            Katib(http=fresh).projects.list()
        assert caught.value.status == 401
        assert Katib(token=token, http=TestClient(app.app)).projects.list() == []
