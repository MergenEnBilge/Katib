"""Datasets laid out the way people actually have them, connected as a folder.

Each test builds a small dataset on disk in one well-known layout, connects it the way a person
would, and checks that the pictures, classes, shapes and splits all came in -- including the case
that used to fail outright: the same file name in two splits.
"""

import json
import time
import zlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage

from katib.api.app import create_app
from katib.config import Settings
from katib.formats import detect_format, masks

API = "/api/v1"


def picture(path: Path, size: tuple[int, int] = (40, 30), color: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Each picture its own colour: Katib skips a picture whose content it already has, so two
    # identical test pictures would quietly become one.
    shade = color or "#%06x" % (zlib.crc32(str(path).encode()) & 0xFFFFFF)
    PILImage.new("RGB", size, shade).save(path)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def api(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(storage={"data_dir": str(tmp_path / "data")}))) as c:
        yield c


def connect(api: TestClient, folder: Path) -> tuple[str, dict[str, Any]]:
    project = api.post(f"{API}/projects", json={"name": folder.name}).json()["id"]
    made = api.post(f"{API}/projects/{project}/folders", json={"path": str(folder)})
    assert made.status_code == 201, made.text
    job_id = made.json()["job"]["id"]
    for _ in range(500):
        job = api.get(f"{API}/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            assert job["status"] == "done", job
            return project, job["result"]
        time.sleep(0.02)
    raise AssertionError("the import did not finish")


def contents(api: TestClient, project: str) -> dict[str, dict[str, Any]]:
    """Each picture by the folder it sits in and its name: split, and shapes as class/type."""
    classes = {c["id"]: c["name"] for c in api.get(f"{API}/projects/{project}/classes").json()}
    out: dict[str, dict[str, Any]] = {}
    for image in api.get(f"{API}/projects/{project}/images", params={"limit": 500}).json()["items"]:
        shapes = api.get(f"{API}/images/{image['id']}/annotations").json()
        key = f"{image['split']}/{image['filename']}"
        assert key not in out, f"two pictures in {key}"
        out[key] = {
            "split": image["split"],
            "shapes": sorted(f"{classes.get(s['class_id'])}:{s['type']}" for s in shapes),
        }
    return out


def test_ultralytics_with_one_name_in_two_splits(api: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "ultralytics"
    write(
        root / "data.yaml",
        "path: .\ntrain: images/train\nval: images/val\nnames:\n  0: car\n  1: bus\n",
    )
    picture(root / "images" / "train" / "a.jpg", color="red")
    picture(root / "images" / "val" / "a.jpg", color="blue")
    write(root / "labels" / "train" / "a.txt", "0 0.5 0.5 0.2 0.2\n")
    write(root / "labels" / "val" / "a.txt", "1 0.5 0.5 0.4 0.4\n")

    project, result = connect(api, root)

    assert result["dataset"]["format"] == "yolo-detect"
    assert contents(api, project) == {
        "train/a.jpg": {"split": "train", "shapes": ["car:box"]},
        "val/a.jpg": {"split": "val", "shapes": ["bus:box"]},
    }


def test_roboflow_yolo_unpacked_into_a_folder_of_its_own(api: TestClient, tmp_path: Path) -> None:
    outer = tmp_path / "download"
    root = outer / "my-dataset-3"
    write(
        root / "data.yaml",
        "train: ../train/images\nval: ../valid/images\ntest: ../test/images\n"
        "nc: 1\nnames: ['cat']\n",
    )
    for split, folder in (("train", "train"), ("val", "valid"), ("test", "test")):
        picture(root / folder / "images" / f"{split}1.jpg")
        write(root / folder / "labels" / f"{split}1.txt", "0 0.5 0.5 0.3 0.3\n")

    project, _ = connect(api, outer)

    assert contents(api, project) == {
        f"{split}/{split}1.jpg": {"split": split, "shapes": ["cat:box"]}
        for split in ("train", "val", "test")
    }


def test_old_darknet_layout(api: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "darknet"
    write(root / "obj.names", "person\nbike\n")
    write(
        root / "obj.data",
        "classes = 2\ntrain = data/train.txt\nvalid = data/valid.txt\nnames = obj.names\n",
    )
    picture(root / "data" / "obj" / "p1.jpg")
    picture(
        root / "data" / "obj" / "p2.jpg",
    )
    write(root / "data" / "obj" / "p1.txt", "0 0.5 0.5 0.2 0.4\n")
    write(root / "data" / "obj" / "p2.txt", "1 0.4 0.4 0.2 0.2\n0 0.6 0.6 0.1 0.1\n")
    write(root / "data" / "train.txt", "data/obj/p1.jpg\n")
    write(root / "data" / "valid.txt", "data/obj/p2.jpg\n")

    project, result = connect(api, root)

    assert result["dataset"]["format"] == "yolo-detect"
    assert result["dataset"]["notes"] == []  # list files are not misread as labels
    assert contents(api, project) == {
        "train/p1.jpg": {"split": "train", "shapes": ["person:box"]},
        "val/p2.jpg": {"split": "val", "shapes": ["bike:box", "person:box"]},
    }


def test_yolo_pose_reads_keypoints(api: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "pose"
    write(root / "data.yaml", "train: images\nval: images\nkpt_shape: [3, 3]\nnames: {0: person}\n")
    picture(root / "images" / "p.jpg")
    write(
        root / "labels" / "p.txt",
        "0 0.5 0.5 0.4 0.6 0.4 0.3 2 0.6 0.3 1 0.5 0.7 0\n",
    )

    project, result = connect(api, root)

    assert result["dataset"]["format"] == "yolo-pose"
    image = api.get(f"{API}/projects/{project}/images").json()["items"][0]
    (shape,) = api.get(f"{API}/images/{image['id']}/annotations").json()
    assert shape["type"] == "keypoints"
    assert [p["v"] for p in shape["geometry"]["points"]] == [2, 1, 0]


def test_yolo_rotated_boxes_are_recognised(tmp_path: Path) -> None:
    root = tmp_path / "obb"
    write(root / "data.yaml", "train: images\nval: images\nnames: ['ship']\n")
    write(root / "labels" / "s.txt", "0 0.2 0.2 0.6 0.2 0.6 0.5 0.2 0.5\n")
    assert detect_format(root).id == "yolo-obb"


def test_roboflow_coco_with_a_file_per_split(api: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "coco"
    for folder, split in (("train", "train"), ("valid", "val")):
        picture(root / folder / "x.jpg", (100, 50), color="red" if split == "train" else "blue")
        doc = {
            "images": [{"id": 1, "file_name": "x.jpg", "width": 100, "height": 50}],
            "categories": [{"id": 1, "name": "dog"}],
            "annotations": [{"id": 1, "image_id": 1, "category_id": 1, "bbox": [10, 10, 20, 20]}],
        }
        write(root / folder / "_annotations.coco.json", json.dumps(doc))

    project, result = connect(api, root)

    assert result["dataset"]["format"] == "coco"
    assert contents(api, project) == {
        "train/x.jpg": {"split": "train", "shapes": ["dog:box"]},
        "val/x.jpg": {"split": "val", "shapes": ["dog:box"]},
    }


def test_voc_devkit_with_trainval(api: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "VOCdevkit"
    year = root / "VOC2012"
    picture(year / "JPEGImages" / "2007_000027.jpg", (100, 80))
    write(
        year / "Annotations" / "2007_000027.xml",
        "<annotation><filename>2007_000027.jpg</filename><size><width>100</width>"
        "<height>80</height></size><object><name>person</name><bndbox><xmin>10</xmin>"
        "<ymin>10</ymin><xmax>50</xmax><ymax>60</ymax></bndbox></object></annotation>",
    )
    write(year / "ImageSets" / "Main" / "trainval.txt", "2007_000027\n")

    project, result = connect(api, root)

    assert result["dataset"]["format"] == "voc"
    assert contents(api, project) == {
        "train/2007_000027.jpg": {"split": "train", "shapes": ["person:box"]},
    }


def test_labelme_in_split_folders_with_circles_and_points(api: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "labelme"
    picture(root / "val" / "m.jpg", (100, 100))
    doc = {
        "imagePath": "m.jpg",
        "imageWidth": 100,
        "imageHeight": 100,
        "shapes": [
            {"label": "ball", "shape_type": "circle", "points": [[50, 50], [60, 50]]},
            {"label": "nose", "shape_type": "point", "points": [[20, 30]]},
            {"label": "edge", "shape_type": "line", "points": [[0, 0], [10, 10]]},
        ],
    }
    write(root / "val" / "m.json", json.dumps(doc))

    project, result = connect(api, root)

    assert result["dataset"]["format"] == "labelme"
    assert contents(api, project) == {
        "val/m.jpg": {"split": "val", "shapes": ["ball:polygon", "nose:keypoints"]}
    }
    assert any("no line shape" in n["reason"] for n in result["dataset"]["notes"])


def test_cvat_xml_with_subsets(api: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "cvat"
    picture(root / "images" / "c.jpg", (200, 100))
    write(
        root / "annotations.xml",
        """<annotations><version>1.1</version>
        <meta><task><labels><label><name>car</name></label><label><name>road</name></label>
        </labels></task></meta>
        <image id="0" name="c.jpg" width="200" height="100" subset="Validation">
          <box label="car" xtl="10" ytl="10" xbr="60" ybr="40" />
          <polygon label="road" points="0,90;200,90;200,100;0,100" />
          <tag label="car" />
        </image></annotations>""",
    )

    project, result = connect(api, root)

    assert result["dataset"]["format"] == "cvat"
    assert contents(api, project) == {
        "val/c.jpg": {"split": "val", "shapes": ["car:box", "car:tag", "road:polygon"]}
    }


def test_createml_per_split(api: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "createml"
    picture(root / "train" / "k.jpg", (100, 100))
    doc = [
        {
            "image": "k.jpg",
            "annotations": [
                {"label": "kite", "coordinates": {"x": 50, "y": 50, "width": 20, "height": 10}}
            ],
        }
    ]
    write(root / "train" / "_annotations.createml.json", json.dumps(doc))

    project, result = connect(api, root)

    assert result["dataset"]["format"] == "createml"
    assert contents(api, project) == {"train/k.jpg": {"split": "train", "shapes": ["kite:box"]}}


def test_class_per_folder(api: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "pets"
    for split in ("train", "val"):
        picture(
            root / split / "cat" / f"{split}-c.jpg",
        )
        picture(
            root / split / "dog" / f"{split}-d.jpg",
        )

    project, result = connect(api, root)

    assert result["dataset"]["format"] == "class-folders"
    assert contents(api, project) == {
        "train/train-c.jpg": {"split": "train", "shapes": ["cat:tag"]},
        "train/train-d.jpg": {"split": "train", "shapes": ["dog:tag"]},
        "val/val-c.jpg": {"split": "val", "shapes": ["cat:tag"]},
        "val/val-d.jpg": {"split": "val", "shapes": ["dog:tag"]},
    }


def test_a_photo_library_is_not_mistaken_for_class_folders(tmp_path: Path) -> None:
    root = tmp_path / "photos"
    picture(root / "Paris" / "1.jpg")
    picture(root / "Rome" / "2.jpg")
    with pytest.raises(ValueError):
        detect_format(root)


def test_segmentation_masks_saved_as_pictures(api: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "seg"
    picture(root / "images" / "r.png", (8, 4))
    write(root / "classes.txt", "background\nroad\ncar\n")
    mask = PILImage.new("L", (8, 4), 0)
    for x in range(8):
        mask.putpixel((x, 3), 1)  # the bottom row is road
    mask.putpixel((2, 1), 2)  # one pixel of car
    (root / "masks").mkdir(parents=True)
    mask.save(root / "masks" / "r.png")

    project, result = connect(api, root)

    assert result["dataset"]["format"] == "mask-png"
    assert contents(api, project)["None/r.png"]["shapes"] == ["car:mask", "road:mask"]


def _coco_string(counts: list[int]) -> str:
    """COCO's compact text form, written the way pycocotools writes it."""
    out = []
    for i, value in enumerate(counts):
        x = value - counts[i - 2] if i > 2 else value
        more = True
        while more:
            c = x & 0x1F
            x >>= 5
            more = (x != -1) if (c & 0x10) else (x != 0)
            if more:
                c |= 0x20
            out.append(chr(c + 48))
    return "".join(out)


def test_coco_compact_run_lengths_are_read() -> None:
    counts = [3, 3, 6, 120, 4, 7]
    assert masks.coco_counts(_coco_string(counts)) == counts


def test_a_folder_of_photos_called_masks_is_still_photos(api: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "carnival"
    picture(root / "masks" / "venice.png")
    picture(root / "masks" / "rio.png")
    picture(root / "crowds" / "street.png")

    project, _ = connect(api, root)

    assert len(contents(api, project)) == 3
