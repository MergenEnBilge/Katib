from collections.abc import Iterable
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from katib.core.dataset import ExportImage, ExportOptions, ParsedDataset, Shape
from katib.formats import FormatError, detect_format, get_format

GOLDEN = Path(__file__).parent / "golden"


class View:
    """A DatasetView built from a parsed dataset, for round-trip tests."""

    def __init__(self, data: ParsedDataset, size: tuple[int, int] = (200, 100)) -> None:
        self.class_names = data.class_names
        self.skeletons = data.skeletons
        self._data = data
        self._size = size

    def images(self) -> Iterable[ExportImage]:
        for img in self._data.images:
            yield ExportImage(
                img.filename, img.width or self._size[0], img.height or self._size[1], img.shapes
            )


def shapes_of(data: ParsedDataset) -> dict[str, list[tuple[str, str, dict[str, object]]]]:
    return {
        Path(i.filename).stem: [(s.class_name, s.type, s.geometry) for s in i.shapes]
        for i in data.images
    }


def approx_equal(a: object, b: object) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(approx_equal(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(approx_equal(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) < 1e-4
    return a == b


def assert_same(a: ParsedDataset, b: ParsedDataset) -> None:
    sa, sb = shapes_of(a), shapes_of(b)
    assert sa.keys() == sb.keys()
    for key in sa:
        assert len(sa[key]) == len(sb[key]), key
        for x, y in zip(sa[key], sb[key], strict=True):
            assert x[:2] == y[:2]
            assert approx_equal(x[2], y[2]), (key, x, y)


def test_yolo_golden_read() -> None:
    fmt = get_format("yolo-detect")
    data = fmt.read(GOLDEN / "yolo")
    assert data.class_names == ["car", "bus"]
    shapes = shapes_of(data)
    assert set(shapes) == {"street1", "street2", "empty"}
    assert shapes["empty"] == []
    car = shapes["street1"][0]
    assert car[0] == "car"
    assert approx_equal(car[2], {"x": 0.2, "y": 0.2, "w": 0.2, "h": 0.4})
    assert data.notes == []


def test_yolo_round_trip(tmp_path: Path) -> None:
    fmt = get_format("yolo-detect")
    original = fmt.read(GOLDEN / "yolo")
    report = fmt.write(View(original), tmp_path, ExportOptions())
    assert report.images == 3 and report.shapes == 3
    assert (tmp_path / "data.yaml").is_file()
    assert_same(original, fmt.read(tmp_path))


def test_yolo_bad_lines_are_reported_not_dropped_silently(tmp_path: Path) -> None:
    (tmp_path / "labels").mkdir()
    (tmp_path / "classes.txt").write_text("car\n")
    (tmp_path / "labels" / "a.txt").write_text(
        "0 0.5 0.5 0.2 0.2\nx y z\n7 0.5 0.5 0.1 0.1\n0 0.1 0.1 0.2 0.2 0.3 0.3\n"
    )
    data = get_format("yolo-detect").read(tmp_path)
    assert len(data.images[0].shapes) == 1
    assert len(data.notes) == 3
    assert "not numbers" in data.notes[0].reason
    assert "not in the class list" in data.notes[1].reason


def test_yolo_without_class_names_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "labels").mkdir()
    with pytest.raises(FormatError, match="class names"):
        get_format("yolo-detect").read(tmp_path)


def test_yolo_export_writes_polygon_as_bbox_and_says_so(tmp_path: Path) -> None:
    poly = Shape("car", "polygon", {"points": [[0.1, 0.1], [0.5, 0.1], [0.3, 0.6]]})
    data = ParsedDataset(["car"], [])
    view = View(data)
    view.images = lambda: [ExportImage("a.jpg", 100, 100, [poly])]  # type: ignore[method-assign]
    report = get_format("yolo-detect").write(view, tmp_path, ExportOptions())
    assert report.shapes == 1
    assert "bounding box" in report.notes[0].reason
    assert (tmp_path / "labels" / "a.txt").read_text().startswith("0 0.300000 0.350000")


def test_duplicate_filenames_do_not_overwrite(tmp_path: Path) -> None:
    box = Shape("car", "box", {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2})
    view = View(ParsedDataset(["car"], []))
    view.images = lambda: [  # type: ignore[method-assign]
        ExportImage("a.jpg", 10, 10, [box]),
        ExportImage("sub/a.jpg", 10, 10, [box, box]),
    ]
    get_format("yolo-detect").write(view, tmp_path, ExportOptions())
    assert sorted(p.name for p in (tmp_path / "labels").iterdir()) == ["a.txt", "a_2.txt"]


def test_coco_golden_read() -> None:
    data = get_format("coco").read(GOLDEN / "coco" / "annotations.json")
    assert data.class_names == ["car", "bus"]
    shapes = shapes_of(data)
    assert set(shapes) == {"street1", "street2"}
    kinds = [(s[0], s[1]) for s in shapes["street1"]]
    assert kinds == [("car", "box"), ("bus", "polygon")]
    assert approx_equal(shapes["street1"][0][2], {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.3})
    assert shapes["street2"][0][2] == {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
    assert [i.filename for i in data.images] == ["street1.jpg", "street2.jpg"]


def test_coco_round_trip(tmp_path: Path) -> None:
    fmt = get_format("coco")
    original = fmt.read(GOLDEN / "coco")
    fmt.write(View(original), tmp_path, ExportOptions())
    assert_same(original, fmt.read(tmp_path / "annotations.json"))


def test_coco_ids_follow_class_order(tmp_path: Path) -> None:
    import json

    fmt = get_format("coco")
    fmt.write(View(fmt.read(GOLDEN / "coco")), tmp_path, ExportOptions())
    doc = json.loads((tmp_path / "annotations.json").read_text())
    assert doc["categories"] == [{"id": 1, "name": "car"}, {"id": 2, "name": "bus"}]


def test_coco_reports_masks_and_multi_ring_polygons(tmp_path: Path) -> None:
    import json

    doc = {
        "images": [{"id": 1, "file_name": "a.jpg", "width": 100, "height": 100}],
        "categories": [{"id": 1, "name": "car"}],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 1, "iscrowd": 1, "bbox": [0, 0, 1, 1]},
            {
                "id": 2, "image_id": 1, "category_id": 1,
                "segmentation": [[10, 10, 50, 10, 50, 50], [60, 60, 90, 60, 90, 90]],
            },
            {"id": 3, "image_id": 9, "category_id": 1, "bbox": [0, 0, 1, 1]},
        ],
    }  # fmt: skip
    file = tmp_path / "c.json"
    file.write_text(json.dumps(doc))
    data = get_format("coco").read(file)
    assert len(data.images[0].shapes) == 2
    reasons = " | ".join(n.reason for n in data.notes)
    assert "Run-length" in reasons and "Split into 2" in reasons and "not listed" in reasons


def test_detection() -> None:
    assert detect_format(GOLDEN / "coco" / "annotations.json").id == "coco"
    assert detect_format(GOLDEN / "yolo").id == "yolo-detect"
    with pytest.raises(FormatError):
        detect_format(GOLDEN)


def test_not_a_coco_file(tmp_path: Path) -> None:
    file = tmp_path / "x.json"
    file.write_text('{"hello": 1}')
    with pytest.raises(FormatError, match="COCO"):
        get_format("coco").read(file)


@st.composite
def boxes(draw: st.DrawFn) -> dict[str, float]:
    w = draw(st.floats(0.01, 1.0))
    h = draw(st.floats(0.01, 1.0))
    return {
        "x": draw(st.floats(0.0, 1.0 - w)),
        "y": draw(st.floats(0.0, 1.0 - h)),
        "w": w,
        "h": h,
    }


@given(st.lists(boxes(), min_size=1, max_size=8))
def test_box_round_trip_property(
    tmp_path_factory: pytest.TempPathFactory, geoms: list[dict[str, float]]
) -> None:
    shapes = [Shape("car", "box", g) for g in geoms]
    src = ParsedDataset(["car"], [])
    view = View(src, (640, 480))
    view.images = lambda: [ExportImage("p.jpg", 640, 480, shapes)]  # type: ignore[method-assign]
    for fmt_id, target in (("yolo-detect", None), ("coco", "annotations.json")):
        out = tmp_path_factory.mktemp("rt")
        fmt = get_format(fmt_id)
        fmt.write(view, out, ExportOptions())
        back = fmt.read(out / target if target else out)
        got = back.images[0].shapes
        assert len(got) == len(shapes)
        for a, b in zip(shapes, got, strict=True):
            assert all(abs(a.geometry[k] - b.geometry[k]) < 1e-3 for k in "xywh")


def test_yolo_split_export_layout_and_data_yaml(tmp_path: Path) -> None:
    import yaml

    box = Shape("car", "box", {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2})
    view = View(ParsedDataset(["car"], []))
    view.images = lambda: [  # type: ignore[method-assign]
        ExportImage("a.jpg", 10, 10, [box], split="train"),
        ExportImage("b.jpg", 10, 10, [box], split="val"),
        ExportImage("c.jpg", 10, 10, [], split="test"),
    ]
    get_format("yolo-detect").write(view, tmp_path, ExportOptions())
    assert (tmp_path / "labels" / "train" / "a.txt").is_file()
    assert (tmp_path / "labels" / "val" / "b.txt").is_file()
    assert (tmp_path / "labels" / "test" / "c.txt").is_file()
    data = yaml.safe_load((tmp_path / "data.yaml").read_text())
    assert data["train"] == "images/train"
    assert data["val"] == "images/val"
    assert data["test"] == "images/test"
    assert data["names"] == {0: "car"}


def test_coco_split_export_writes_one_file_per_split(tmp_path: Path) -> None:
    import json

    box = Shape("car", "box", {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2})
    view = View(ParsedDataset(["car"], []))
    view.images = lambda: [  # type: ignore[method-assign]
        ExportImage("a.jpg", 10, 10, [box], split="train"),
        ExportImage("b.jpg", 10, 10, [box, box], split="val"),
    ]
    get_format("coco").write(view, tmp_path, ExportOptions())
    train = json.loads((tmp_path / "annotations_train.json").read_text())
    val = json.loads((tmp_path / "annotations_val.json").read_text())
    assert len(train["annotations"]) == 1 and len(val["annotations"]) == 2
    assert [c["name"] for c in val["categories"]] == ["car"]
    train_ids = {a["id"] for a in train["annotations"]}
    assert train_ids.isdisjoint({a["id"] for a in val["annotations"]})


def test_yolo_reads_splits_from_the_folder_layout(tmp_path: Path) -> None:
    (tmp_path / "data.yaml").write_text("names: [car]\n")
    for split, name in (("train", "a"), ("valid", "b")):
        (tmp_path / "labels" / split).mkdir(parents=True)
        (tmp_path / "labels" / split / f"{name}.txt").write_text("0 0.5 0.5 0.2 0.2\n")
    (tmp_path / "labels" / "c.txt").write_text("0 0.5 0.5 0.2 0.2\n")
    got = {i.filename: i.split for i in get_format("yolo-detect").read(tmp_path).images}
    assert got == {"a": "train", "b": "val", "c": None}


def test_yolo_reads_splits_from_list_files(tmp_path: Path) -> None:
    (tmp_path / "data.yaml").write_text("names: [car]\ntrain: train.txt\nval: val.txt\n")
    (tmp_path / "train.txt").write_text("./images/a.jpg\n")
    (tmp_path / "val.txt").write_text("./images/b.jpg\n")
    (tmp_path / "labels").mkdir()
    for name in "ab":
        (tmp_path / "labels" / f"{name}.txt").write_text("0 0.5 0.5 0.2 0.2\n")
    got = {i.filename: i.split for i in get_format("yolo-detect").read(tmp_path).images}
    assert got == {"a": "train", "b": "val"}


def test_a_yolo_export_reads_back_with_its_splits(tmp_path: Path) -> None:
    box = Shape("car", "box", {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2})
    view = View(ParsedDataset(["car"], []))
    view.images = lambda: [  # type: ignore[method-assign]
        ExportImage("a.jpg", 10, 10, [box], split="train"),
        ExportImage("b.jpg", 10, 10, [box], split="test"),
    ]
    get_format("yolo-detect").write(view, tmp_path, ExportOptions())
    got = {i.filename: i.split for i in get_format("yolo-detect").read(tmp_path).images}
    assert got == {"a": "train", "b": "test"}
