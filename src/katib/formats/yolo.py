"""YOLO formats: one .txt per image with a class index and normalized numbers, plus data.yaml.

Three flavors share the same folder layout and differ only in what a line holds:

- detection: `class cx cy w h`
- segmentation: `class x1 y1 x2 y2 ...` (a polygon)
- oriented boxes: `class x1 y1 x2 y2 x3 y3 x4 y4` (the four corners)
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from katib.core.dataset import (
    DatasetView,
    ExportImage,
    ExportOptions,
    ExportReport,
    ImageLabels,
    Note,
    ParsedDataset,
    Shape,
)
from katib.core.geometry import (
    box_to_polygon,
    box_to_yolo,
    obb_from_corners,
    obb_to_polygon,
    polygon_to_box,
    yolo_to_box,
)
from katib.core.split import SPLITS, split_from_names
from katib.core.types import Box, GeometryError, Obb, Polygon, validate_geometry
from katib.formats.common import FormatError, copy_image, unique_names

YAML_NAMES = ("data.yaml", "dataset.yaml", "data.yml")
IGNORED_TXT = {"classes.txt", "readme.txt", "notes.txt"}
_SPLIT_ORDER = ("train", "val", "test")


def _split_order(name: str | None) -> int:
    return _SPLIT_ORDER.index(name) if name in _SPLIT_ORDER else len(_SPLIT_ORDER)


def _class_names(root: Path) -> list[str]:
    for name in YAML_NAMES:
        path = root / name
        if path.is_file():
            data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
            names = data.get("names") if isinstance(data, dict) else None
            if isinstance(names, dict):
                return [str(names[k]) for k in sorted(names, key=int)]
            if isinstance(names, list):
                return [str(n) for n in names]
    classes = root / "classes.txt"
    if classes.is_file():
        return [ln.strip() for ln in classes.read_text(encoding="utf-8").splitlines() if ln.strip()]
    raise FormatError("No class names found. Add a data.yaml with a names list or a classes.txt.")


def _yaml_data(root: Path) -> dict[str, Any]:
    for name in YAML_NAMES:
        path = root / name
        if path.is_file():
            data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    return {}


def _listed_splits(root: Path) -> dict[str, str]:
    """Splits named by list files, when data.yaml says `train: train.txt`. Keys are image stems."""
    data = _yaml_data(root)
    base = root / str(data["path"]) if data.get("path") else root
    listed: dict[str, str] = {}
    for split in SPLITS:
        entry = data.get("valid" if split == "val" and "val" not in data else split)
        if not isinstance(entry, str) or not entry.endswith(".txt"):
            continue
        file = base / entry
        if file.is_file():
            for line in file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    listed[Path(line.strip()).stem.lower()] = split
    return listed


def _label_files(root: Path) -> list[Path]:
    base = root / "labels" if (root / "labels").is_dir() else root
    return sorted(p for p in base.rglob("*.txt") if p.name.lower() not in IGNORED_TXT)


def _has_yolo_layout(path: Path) -> bool:
    if not path.is_dir():
        return False
    has_yaml = any((path / n).is_file() for n in YAML_NAMES)
    return has_yaml or (path / "classes.txt").is_file() or (path / "labels").is_dir()


def _clip(value: float) -> float:
    return min(1.0, max(0.0, value))


class _YoloFamily:
    """Reading and writing shared by every flavor. Subclasses say what one line holds."""

    id: str
    label: str
    supports: frozenset[str]

    def detect(self, path: Path) -> bool:
        return _has_yolo_layout(path)

    def _shape_from(
        self, index: int, values: list[float], names: list[str], size: tuple[int, int] | None
    ) -> Shape:
        """Turn one line's numbers into a shape. Raise ValueError with a reason to skip it."""
        raise NotImplementedError

    def _line_for(
        self, shape: Shape, index: int, img: ExportImage, report: ExportReport
    ) -> str | None:
        """The text for one shape, or None when this flavor cannot hold it."""
        raise NotImplementedError

    def read(self, path: Path, sizes: Mapping[str, tuple[int, int]] | None = None) -> ParsedDataset:
        if not path.is_dir():
            raise FormatError("Choose the folder that holds data.yaml and the labels.")
        names = _class_names(path)
        result = ParsedDataset(class_names=names, images=[])
        listed = _listed_splits(path)
        for file in _label_files(path):
            folders = file.relative_to(path).parts[:-1]
            labels = ImageLabels(
                filename=file.stem,
                split=listed.get(file.stem.lower()) or split_from_names(folders),
            )
            size = (sizes or {}).get(file.stem.lower())
            lines = file.read_text(encoding="utf-8").splitlines()
            for number, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                where = f"{file.name}:{number}"
                try:
                    parts = line.split()
                    index = int(parts[0])
                    values = [float(v) for v in parts[1:]]
                except ValueError:
                    result.notes.append(Note(where, "Line is not numbers."))
                    continue
                if not 0 <= index < len(names):
                    result.notes.append(
                        Note(where, f"Class index {index} is not in the class list.")
                    )
                    continue
                try:
                    labels.shapes.append(self._shape_from(index, values, names, size))
                except (ValueError, GeometryError) as err:
                    result.notes.append(Note(where, str(err)))
            result.images.append(labels)
        return result

    def write(self, view: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport:
        report = ExportReport()
        names = view.class_names
        index = {n: i for i, n in enumerate(names)}
        images = list(view.images())
        splits = sorted({i.split for i in images if i.split}, key=_split_order)
        (dest / "labels").mkdir(parents=True, exist_ok=True)
        for img, name in zip(images, unique_names(images), strict=True):
            part = img.split or ""
            lines: list[str] = []
            for shape in img.shapes:
                line = self._line_for(shape, index[shape.class_name], img, report)
                if line is not None:
                    lines.append(line)
            label_dir = dest / "labels" / part
            label_dir.mkdir(parents=True, exist_ok=True)
            (label_dir / f"{Path(name).stem}.txt").write_text(
                "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
            )
            if opts.copy_images and img.source is not None:
                copy_image(img.source, dest / "images" / part, name)
            report.images += 1
            report.shapes += len(lines)
        data: dict[str, Any] = {"path": "."}
        if splits:
            for split in splits:
                data[split] = f"images/{split}"
            data.setdefault("val", data.get("train", "images"))
        else:
            data.update(train="images", val="images")
        data["names"] = dict(enumerate(names))
        (dest / "data.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return report


def _numbers(index: int, points: list[tuple[float, float]]) -> str:
    return f"{index} " + " ".join(f"{x:.6f} {y:.6f}" for x, y in points)


def _geometry(shape: Shape, img: ExportImage, report: ExportReport) -> Box | Polygon | Obb | None:
    try:
        parsed = validate_geometry(shape.type, shape.geometry)
    except GeometryError as err:
        report.notes.append(Note(img.filename, str(err)))
        return None
    if isinstance(parsed, (Box, Polygon, Obb)):
        return parsed
    report.notes.append(Note(img.filename, f"A {shape.type} cannot be written in this format."))
    return None


class YoloDetect(_YoloFamily):
    id = "yolo-detect"
    label = "YOLO (detection)"
    supports = frozenset({"box"})

    def _shape_from(
        self, index: int, values: list[float], names: list[str], size: tuple[int, int] | None
    ) -> Shape:
        if len(values) != 4:
            raise ValueError("Only 5-value box lines are supported in this format.")
        try:
            box = yolo_to_box(*values)
        except ValueError:
            raise ValueError("Box is empty or outside the image.") from None
        return Shape(names[index], "box", box.model_dump())

    def _line_for(
        self, shape: Shape, index: int, img: ExportImage, report: ExportReport
    ) -> str | None:
        geometry = _geometry(shape, img, report)
        if isinstance(geometry, Box):
            box = geometry
        elif isinstance(geometry, Polygon):
            report.notes.append(Note(img.filename, "Polygon written as its bounding box."))
            box = polygon_to_box(geometry)
        elif isinstance(geometry, Obb):
            report.notes.append(Note(img.filename, "Rotated box written as its bounding box."))
            box = polygon_to_box(obb_to_polygon(geometry, img.width, img.height))
        else:
            return None
        cx, cy, w, h = box_to_yolo(box)
        return f"{index} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


class YoloSegment(_YoloFamily):
    id = "yolo-segment"
    label = "YOLO (segmentation)"
    supports = frozenset({"polygon", "box"})

    def detect(self, path: Path) -> bool:
        """Only claim folders where a label line holds a polygon, so detection sets stay YOLO."""
        if not _has_yolo_layout(path):
            return False
        for file in _label_files(path):
            for line in file.read_text(encoding="utf-8").splitlines():
                if len(line.split()) > 5:
                    return True
        return False

    def _shape_from(
        self, index: int, values: list[float], names: list[str], size: tuple[int, int] | None
    ) -> Shape:
        if len(values) < 6 or len(values) % 2:
            raise ValueError("A polygon line needs at least three x y pairs.")
        points = [(_clip(values[i]), _clip(values[i + 1])) for i in range(0, len(values), 2)]
        return Shape(names[index], "polygon", Polygon(points=points).model_dump())

    def _line_for(
        self, shape: Shape, index: int, img: ExportImage, report: ExportReport
    ) -> str | None:
        geometry = _geometry(shape, img, report)
        if isinstance(geometry, Polygon):
            return _numbers(index, list(geometry.points))
        if isinstance(geometry, Box):
            report.notes.append(Note(img.filename, "Box written as a four point polygon."))
            return _numbers(index, list(box_to_polygon(geometry).points))
        if isinstance(geometry, Obb):
            polygon = obb_to_polygon(geometry, img.width, img.height)
            return _numbers(index, list(polygon.points))
        return None


class YoloObb(_YoloFamily):
    id = "yolo-obb"
    label = "YOLO (oriented boxes)"
    supports = frozenset({"obb", "box"})

    def _shape_from(
        self, index: int, values: list[float], names: list[str], size: tuple[int, int] | None
    ) -> Shape:
        if len(values) != 8:
            raise ValueError("A rotated box line has the four corners: 8 numbers after the class.")
        width, height = size or (1, 1)
        corners = [(_clip(values[i]), _clip(values[i + 1])) for i in range(0, 8, 2)]
        return Shape(names[index], "obb", obb_from_corners(corners, width, height).model_dump())

    def _line_for(
        self, shape: Shape, index: int, img: ExportImage, report: ExportReport
    ) -> str | None:
        geometry = _geometry(shape, img, report)
        if isinstance(geometry, Obb):
            polygon = obb_to_polygon(geometry, img.width, img.height)
            return _numbers(index, list(polygon.points))
        if isinstance(geometry, Box):
            return _numbers(index, list(box_to_polygon(geometry).points))
        if isinstance(geometry, Polygon):
            report.notes.append(Note(img.filename, "Polygons cannot be written as rotated boxes."))
        return None
