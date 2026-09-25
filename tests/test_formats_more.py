import math
from collections.abc import Iterable
from pathlib import Path

import pytest

from katib.core.dataset import (
    ExportImage,
    ExportOptions,
    ParsedDataset,
    Shape,
    SkeletonSpec,
)
from katib.formats import detect_format, get_format

SIZE = (200, 100)


class View:
    def __init__(
        self,
        names: list[str],
        shapes: list[Shape],
        skeletons: dict[str, SkeletonSpec] | None = None,
    ) -> None:
        self.class_names = names
        self.skeletons = skeletons or {}
        self._shapes = shapes

    def images(self) -> Iterable[ExportImage]:
        yield ExportImage("one.jpg", SIZE[0], SIZE[1], self._shapes)


BOX = Shape("car", "box", {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4})
POLYGON = Shape("car", "polygon", {"points": [[0.1, 0.1], [0.5, 0.1], [0.3, 0.6]]})
TURNED = Shape("car", "obb", {"cx": 0.5, "cy": 0.5, "w": 0.4, "h": 0.2, "angle": 0.6})
POSE = Shape(
    "person",
    "keypoints",
    {"points": [{"x": 0.2, "y": 0.2, "v": 2}, {"x": 0.4, "y": 0.5, "v": 1}]},
)


def round_trip(format_id: str, view: View, folder: Path) -> ParsedDataset:
    fmt = get_format(format_id)
    fmt.write(view, folder, ExportOptions())
    return fmt.read(folder, {"one": SIZE})


def test_yolo_segment_keeps_polygons(tmp_path: Path) -> None:
    back = round_trip("yolo-segment", View(["car"], [POLYGON]), tmp_path)
    [shape] = back.images[0].shapes
    assert shape.type == "polygon"
    flat = [c for point in shape.geometry["points"] for c in point]
    assert flat == pytest.approx([0.1, 0.1, 0.5, 0.1, 0.3, 0.6])


def test_yolo_segment_writes_a_box_as_four_points(tmp_path: Path) -> None:
    fmt = get_format("yolo-segment")
    report = fmt.write(View(["car"], [BOX]), tmp_path, ExportOptions())
    line = (tmp_path / "labels" / "one.txt").read_text().split()
    assert len(line) == 1 + 8
    assert any("four point polygon" in n.reason for n in report.notes)


def test_yolo_obb_keeps_center_size_and_angle(tmp_path: Path) -> None:
    back = round_trip("yolo-obb", View(["car"], [TURNED]), tmp_path)
    [shape] = back.images[0].shapes
    assert shape.type == "obb"
    for key, value in TURNED.geometry.items():
        assert shape.geometry[key] == pytest.approx(value, abs=1e-4)


def test_yolo_obb_rejects_lines_without_four_corners(tmp_path: Path) -> None:
    (tmp_path / "labels").mkdir()
    (tmp_path / "labels" / "one.txt").write_text("0 0.1 0.1 0.2 0.2 0.3 0.3\n")
    (tmp_path / "data.yaml").write_text("names: [car]\n")
    back = get_format("yolo-obb").read(tmp_path)
    assert back.images[0].shapes == []
    assert "four corners" in back.notes[0].reason


def test_folder_with_polygon_lines_is_detected_as_segmentation(tmp_path: Path) -> None:
    round_trip("yolo-segment", View(["car"], [POLYGON]), tmp_path)
    assert detect_format(tmp_path).id == "yolo-segment"


def test_folder_with_box_lines_is_still_detected_as_detection(tmp_path: Path) -> None:
    round_trip("yolo-detect", View(["car"], [BOX]), tmp_path)
    assert detect_format(tmp_path).id == "yolo-detect"


def test_voc_round_trip_keeps_boxes_to_the_pixel(tmp_path: Path) -> None:
    back = round_trip("voc", View(["car"], [BOX]), tmp_path)
    assert detect_format(tmp_path).id == "voc"
    [shape] = back.images[0].shapes
    assert shape.geometry == pytest.approx(BOX.geometry, abs=0.01)
    assert back.class_names == ["car"]


def test_voc_file_with_an_xml_bomb_is_refused_not_expanded(tmp_path: Path) -> None:
    bomb = (
        '<?xml version="1.0"?><!DOCTYPE annotation [<!ENTITY a "aaaaaaaaaa">'
        '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]><annotation><filename>&b;</filename></annotation>'
    )
    (tmp_path / "bad.xml").write_text(bomb)
    back = get_format("voc").read(tmp_path)
    assert back.images == []
    assert back.notes[0].reason == "Not a VOC annotation file."


def test_labelme_round_trip_keeps_boxes_and_polygons(tmp_path: Path) -> None:
    back = round_trip("labelme", View(["car"], [BOX, POLYGON]), tmp_path)
    assert detect_format(tmp_path).id == "labelme"
    kinds = [s.type for s in back.images[0].shapes]
    assert kinds == ["box", "polygon"]
    assert back.images[0].shapes[0].geometry == pytest.approx(BOX.geometry)


def test_coco_keypoints_round_trip_with_the_skeleton(tmp_path: Path) -> None:
    skeleton = {"person": SkeletonSpec(["nose", "hip"], [(0, 1)])}
    back = round_trip("coco", View(["person"], [POSE], skeleton), tmp_path)
    [shape] = back.images[0].shapes
    assert shape.type == "keypoints"
    assert [p["v"] for p in shape.geometry["points"]] == [2, 1]
    assert shape.geometry["points"][0]["x"] == pytest.approx(0.2)
    assert back.skeletons["person"] == skeleton["person"]


def test_coco_writes_a_rotated_box_as_a_polygon(tmp_path: Path) -> None:
    back = round_trip("coco", View(["car"], [TURNED]), tmp_path)
    [shape] = back.images[0].shapes
    assert shape.type == "polygon"
    xs = [p[0] for p in shape.geometry["points"]]
    assert max(xs) - min(xs) == pytest.approx(
        (0.4 * math.cos(0.6) * 200 + 0.2 * math.sin(0.6) * 100) / 200, abs=0.01
    )
