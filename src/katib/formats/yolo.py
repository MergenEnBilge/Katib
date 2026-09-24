"""YOLO detection format: one .txt per image with `class cx cy w h` lines, plus data.yaml."""

from pathlib import Path
from typing import Any

import yaml

from katib.core.dataset import (
    DatasetView,
    ExportOptions,
    ExportReport,
    ImageLabels,
    Note,
    ParsedDataset,
    Shape,
)
from katib.core.geometry import box_to_yolo, polygon_to_box, yolo_to_box
from katib.core.types import Box, GeometryError, Polygon, validate_geometry
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


def _label_files(root: Path) -> list[Path]:
    base = root / "labels" if (root / "labels").is_dir() else root
    return sorted(p for p in base.rglob("*.txt") if p.name.lower() not in IGNORED_TXT)


class YoloDetect:
    id = "yolo-detect"
    label = "YOLO (detection)"
    supports = frozenset({"box"})

    def detect(self, path: Path) -> bool:
        if not path.is_dir():
            return False
        has_yaml = any((path / n).is_file() for n in YAML_NAMES)
        return has_yaml or (path / "classes.txt").is_file() or (path / "labels").is_dir()

    def read(self, path: Path) -> ParsedDataset:
        if not path.is_dir():
            raise FormatError("Choose the folder that holds data.yaml and the labels.")
        names = _class_names(path)
        result = ParsedDataset(class_names=names, images=[])
        for file in _label_files(path):
            labels = ImageLabels(filename=file.stem)
            lines = file.read_text(encoding="utf-8").splitlines()
            for number, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                shape = self._parse_line(line, names, f"{file.name}:{number}", result.notes)
                if shape:
                    labels.shapes.append(shape)
            result.images.append(labels)
        return result

    def _parse_line(
        self, line: str, names: list[str], where: str, notes: list[Note]
    ) -> Shape | None:
        parts = line.split()
        try:
            index = int(parts[0])
            values = [float(v) for v in parts[1:]]
        except ValueError:
            notes.append(Note(where, "Line is not numbers."))
            return None
        if len(values) != 4:
            notes.append(Note(where, "Only 5-value box lines are supported in this format."))
            return None
        if not 0 <= index < len(names):
            notes.append(Note(where, f"Class index {index} is not in the class list."))
            return None
        try:
            box = yolo_to_box(*values)
        except ValueError:
            notes.append(Note(where, "Box is empty or outside the image."))
            return None
        return Shape(names[index], "box", box.model_dump())

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
                box = self._as_box(shape, f"{img.filename}", report)
                if box is None:
                    continue
                cx, cy, w, h = box_to_yolo(box)
                lines.append(f"{index[shape.class_name]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
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

    def _as_box(self, shape: Shape, where: str, report: ExportReport) -> Box | None:
        try:
            geometry = validate_geometry(shape.type, shape.geometry)
        except GeometryError as err:
            report.notes.append(Note(where, str(err)))
            return None
        if isinstance(geometry, Box):
            return geometry
        if isinstance(geometry, Polygon):
            report.notes.append(Note(where, "Polygon written as its bounding box."))
            return polygon_to_box(geometry)
        return None
