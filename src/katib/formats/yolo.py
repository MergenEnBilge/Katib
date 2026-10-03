"""YOLO formats: one .txt per image with a class index and normalized numbers.

Four flavors share the same files and differ only in what a line holds:

- detection: `class cx cy w h`
- segmentation: `class x1 y1 x2 y2 ...` (a polygon)
- oriented boxes: `class x1 y1 x2 y2 x3 y3 x4 y4` (the four corners)
- pose: `class cx cy w h x1 y1 [v1] x2 y2 [v2] ...`, with `kpt_shape` in data.yaml

Two generations of layout are read, as people actually have them on disk:

- **Ultralytics**: a data.yaml (or dataset.yaml) with `names`, and `train`, `val` and `test` that
  point at image folders, list files, or lists of either. Labels sit in a `labels` folder that
  mirrors `images` (`images/train/a.jpg` and `labels/train/a.txt`), or beside each split's images
  the way Roboflow exports them (`train/images`, `train/labels`).
- **Darknet**: obj.data and obj.names, with `train.txt` and `valid.txt` listing image paths and
  each label file beside its picture.

The splits a dataset declares are kept, so a dataset comes in already divided the way it was.
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
    SkeletonSpec,
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
from katib.core.types import Box, GeometryError, Keypoints, Obb, Polygon, validate_geometry
from katib.formats.common import (
    IMAGE_SUFFIXES,
    FormatError,
    copy_image,
    find_files,
    parent_folders,
    unique_names,
)

YAML_NAMES = ("data.yaml", "dataset.yaml", "data.yml", "dataset.yml")
IGNORED_TXT = {"classes.txt", "readme.txt", "notes.txt", "license.txt"}
#: Darknet's lists of pictures per split, never label files.
LIST_NAMES = {"train.txt", "valid.txt", "val.txt", "test.txt", "trainval.txt"}
_SPLIT_ORDER = ("train", "val", "test")


def _split_order(name: str | None) -> int:
    return _SPLIT_ORDER.index(name) if name in _SPLIT_ORDER else len(_SPLIT_ORDER)


def _yaml_file(root: Path) -> Path | None:
    found = find_files(root, YAML_NAMES)
    return found[0] if found else None


def _yaml_data(root: Path) -> dict[str, Any]:
    file = _yaml_file(root)
    if file is None:
        return {}
    try:
        data: Any = yaml.safe_load(file.read_text(encoding="utf-8"))
    except yaml.YAMLError as err:
        raise FormatError(f"{file.name} is not valid YAML.") from err
    return data if isinstance(data, dict) else {}


def _darknet_data(root: Path) -> dict[str, str]:
    """obj.data's `key = value` lines: classes, train, valid, names, backup."""
    found = find_files(root, ("obj.data",)) or [p for p in root.glob("*.data") if p.is_file()]
    if not found:
        return {}
    values: dict[str, str] = {}
    for line in found[0].read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep:
            values[key.strip().lower()] = value.strip()
    return values


def _resolve(root: Path, entry: str, *bases: Path) -> Path | None:
    """A path a dataset file mentions. Datasets move, so try it as written, then against each
    folder it could be relative to, then by its last parts under the dataset itself."""
    raw = Path(entry)
    for candidate in [raw, *(b / raw for b in bases)]:
        if candidate.exists():
            return candidate
    parts = raw.parts
    for start in range(1, len(parts)):
        candidate = root.joinpath(*parts[start:])
        if candidate.exists():
            return candidate
    return None


def _names_file_lines(file: Path) -> list[str]:
    return [ln.strip() for ln in file.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _class_names(root: Path) -> list[str]:
    data = _yaml_data(root)
    names = data.get("names")
    if isinstance(names, dict):
        return [str(names[k]) for k in sorted(names, key=int)]  # type: ignore[arg-type]
    if isinstance(names, list):
        return [str(n) for n in names]  # type: ignore[union-attr]
    darknet = _darknet_data(root)
    if darknet.get("names"):
        file = _resolve(root, darknet["names"], root)
        if file is not None and file.is_file():
            return _names_file_lines(file)
    for file in find_files(root, ("classes.txt", "obj.names", "_darknet.labels")):
        return _names_file_lines(file)
    named = sorted(root.glob("*.names"))
    if named:
        return _names_file_lines(named[0])
    raise FormatError(
        "No class names found. Add a data.yaml with a names list, or an obj.names or classes.txt."
    )


def _image_stems(folder: Path) -> set[str]:
    return {p.stem.lower() for p in folder.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES}


def _listed_splits(root: Path) -> tuple[dict[str, set[str]], set[Path]]:
    """Which split each picture belongs to, by stem, from what the dataset declares; and the list
    files that declared it, which are not label files.

    A stem in more than one split (a.jpg in both train and val) is left to the folders it sits in.
    """
    listed: dict[str, set[str]] = {}
    list_files: set[Path] = set()

    def note(stem: str, split: str) -> None:
        listed.setdefault(stem, set()).add(split)

    def take(entry: object, split: str, *bases: Path) -> None:
        if isinstance(entry, list):
            for item in entry:  # type: ignore[union-attr]
                take(item, split, *bases)
            return
        if not isinstance(entry, str) or not entry.strip():
            return
        target = _resolve(root, entry.strip(), *bases)
        if target is None:
            return
        if target.is_dir():
            for stem in _image_stems(target):
                note(stem, split)
        elif target.suffix.lower() == ".txt":
            list_files.add(target.resolve())
            for line in target.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    note(Path(line.strip()).stem.lower(), split)

    yaml_file = _yaml_file(root)
    if yaml_file is not None:
        data = _yaml_data(root)
        here = yaml_file.parent
        base = (here / str(data["path"])) if data.get("path") else here
        for split in SPLITS:
            entry = data.get(split)
            if entry is None and split == "val":
                entry = data.get("valid")
            take(entry, split, base, here, root)

    darknet = _darknet_data(root)
    for key, split in (("train", "train"), ("valid", "val"), ("val", "val"), ("test", "test")):
        if darknet.get(key):
            take(darknet[key], split, root)
    # Darknet folders often carry the lists without an obj.data pointing at them.
    for file in find_files(root, LIST_NAMES):
        if file.resolve() not in list_files:
            split = {"trainval.txt": "train", "valid.txt": "val"}.get(file.name.lower())
            take(str(file), split or file.stem.lower(), root)
    return listed, list_files


def _is_label_file(file: Path, list_files: set[Path]) -> bool:
    name = file.name.lower()
    if name in IGNORED_TXT or name in LIST_NAMES or file.resolve() in list_files:
        return False
    # A text file whose first line is not a class number is something else: notes, a list.
    try:
        with file.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    return line.split()[0].isdigit()
    except (OSError, UnicodeDecodeError):
        return False
    return True  # an empty label file: a picture with nothing on it


def _label_files(root: Path, list_files: set[Path] | None = None) -> list[Path]:
    listed = list_files if list_files is not None else _listed_splits(root)[1]
    base = root / "labels" if (root / "labels").is_dir() else root
    return sorted(p for p in base.rglob("*.txt") if _is_label_file(p, listed))


def _dataset_root(path: Path) -> Path:
    """The folder the dataset really starts in. A zip often unpacks into a folder of its own, so
    data.yaml or obj.data can sit a level or two below what was chosen; labels are read from
    there, not from beside unrelated folders."""
    if (path / "labels").is_dir() or any((path / n).is_file() for n in YAML_NAMES):
        return path
    found = find_files(path, (*YAML_NAMES, "obj.data"))
    return found[0].parent if found else path


def yaml_covers(root: Path, folder: Path) -> bool:
    """True when the data.yaml directly in `root` lists `folder` as a split, or as part of one.

    A person often connects the picture folder itself, such as `images/train`, while data.yaml
    sits above it. This tells Katib that the file really describes that folder.
    """
    file = root / "data.yaml"
    if not file.is_file():
        return False
    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return False
    if not isinstance(data, dict):
        return False
    base = (root / str(data.get("path") or ".")).resolve()
    target = folder.resolve()
    for key in ("train", "val", "valid", "test"):
        value = data.get(key)
        for entry in value if isinstance(value, list) else [value]:
            if not isinstance(entry, str):
                continue
            where = (base / entry).resolve()
            if where == target or where in target.parents or target in where.parents:
                return True
    return False


def _has_yolo_layout(path: Path) -> bool:
    if not path.is_dir():
        return False
    if _yaml_file(path) is not None or (path / "labels").is_dir():
        return True
    markers = ("classes.txt", "obj.names", "obj.data", "_darknet.labels")
    return bool(find_files(path, markers)) or any(path.glob("*.names"))


def _sample_lines(path: Path, limit: int = 200) -> list[list[str]]:
    """The first label lines of a dataset, split into words, for telling flavors apart."""
    lines: list[list[str]] = []
    for file in _label_files(path):
        for line in file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                lines.append(line.split())
                if len(lines) >= limit:
                    return lines
    return lines


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

    def _prepare(self, path: Path, result: ParsedDataset) -> None:
        """Anything a flavor needs from data.yaml before reading lines."""

    def read(self, path: Path, sizes: Mapping[str, tuple[int, int]] | None = None) -> ParsedDataset:
        if not path.is_dir():
            raise FormatError("Choose the folder that holds the dataset: its data.yaml and labels.")
        path = _dataset_root(path)
        names = _class_names(path)
        result = ParsedDataset(class_names=names, images=[])
        self._prepare(path, result)
        listed, list_files = _listed_splits(path)
        for file in _label_files(path, list_files):
            folders = parent_folders(file, path)
            declared = listed.get(file.stem.lower(), set())
            labels = ImageLabels(
                filename=file.stem,
                split=next(iter(declared)) if len(declared) == 1 else split_from_names(folders),
                folders=folders,
            )
            size = (sizes or {}).get(file.stem.lower())
            lines = file.read_text(encoding="utf-8").splitlines()
            for number, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                where = f"{'/'.join(folders + (file.name,))}:{number}"
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

    def _yaml_extra(self, view: DatasetView) -> dict[str, Any]:
        return {}

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
        data.update(self._yaml_extra(view))
        data["names"] = dict(enumerate(names))
        (dest / "data.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return report


def _numbers(index: int, points: list[tuple[float, float]]) -> str:
    return f"{index} " + " ".join(f"{x:.6f} {y:.6f}" for x, y in points)


def _geometry(
    shape: Shape, img: ExportImage, report: ExportReport
) -> Box | Polygon | Obb | Keypoints | None:
    try:
        parsed = validate_geometry(shape.type, shape.geometry)
    except GeometryError as err:
        report.notes.append(Note(img.filename, str(err)))
        return None
    if isinstance(parsed, (Box, Polygon, Obb, Keypoints)):
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
            if isinstance(geometry, Keypoints):
                report.notes.append(Note(img.filename, "Keypoints need the YOLO pose format."))
            return None
        cx, cy, w, h = box_to_yolo(box)
        return f"{index} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


def _looks_obb(lines: list[list[str]]) -> bool:
    return bool(lines) and all(len(words) == 9 for words in lines)


class YoloSegment(_YoloFamily):
    id = "yolo-segment"
    label = "YOLO (segmentation)"
    supports = frozenset({"polygon", "box"})

    def detect(self, path: Path) -> bool:
        """Only claim folders where label lines hold polygons, so detection, rotated-box and pose
        sets go to their own flavors."""
        if not _has_yolo_layout(path) or "kpt_shape" in _yaml_data(path):
            return False
        lines = _sample_lines(path)
        return any(len(words) > 5 for words in lines) and not _looks_obb(lines)

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

    def detect(self, path: Path) -> bool:
        """Every line is a class and four corners: nine numbers, nothing else."""
        if not _has_yolo_layout(path) or "kpt_shape" in _yaml_data(path):
            return False
        return _looks_obb(_sample_lines(path))

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


class YoloPose(_YoloFamily):
    """Keypoints, as Ultralytics pose models train on: a box, then each landmark's x, y and,
    when `kpt_shape` says three numbers per landmark, whether it is visible."""

    id = "yolo-pose"
    label = "YOLO (pose keypoints)"
    supports = frozenset({"keypoints"})

    def __init__(self) -> None:
        self._points = 0
        self._dims = 3

    def detect(self, path: Path) -> bool:
        return _has_yolo_layout(path) and "kpt_shape" in _yaml_data(path)

    def _prepare(self, path: Path, result: ParsedDataset) -> None:
        data = _yaml_data(path)
        shape = data.get("kpt_shape")
        if not isinstance(shape, list) or len(shape) != 2:  # type: ignore[arg-type]
            raise FormatError("A pose dataset needs kpt_shape: [landmarks, 2 or 3] in data.yaml.")
        self._points, self._dims = int(shape[0]), int(shape[1])  # type: ignore[index]
        if self._dims not in (2, 3) or self._points < 1:
            raise FormatError("kpt_shape must be [landmarks, 2] or [landmarks, 3].")
        labels = data.get("kpt_names")
        names = (
            [str(n) for n in labels]  # type: ignore[union-attr]
            if isinstance(labels, list) and len(labels) == self._points  # type: ignore[arg-type]
            else [f"point {i + 1}" for i in range(self._points)]
        )
        for name in result.class_names:
            result.skeletons[name] = SkeletonSpec(names, [])

    def _shape_from(
        self, index: int, values: list[float], names: list[str], size: tuple[int, int] | None
    ) -> Shape:
        expected = 4 + self._points * self._dims
        if len(values) != expected:
            raise ValueError(f"A pose line needs {expected} numbers after the class.")
        marks: list[dict[str, Any]] = []
        for i in range(4, expected, self._dims):
            x, y = _clip(values[i]), _clip(values[i + 1])
            visible = int(values[i + 2]) if self._dims == 3 else 2
            if x == 0 and y == 0:
                visible = 0
            marks.append({"x": x, "y": y, "v": max(0, min(2, visible))})
        return Shape(names[index], "keypoints", {"points": marks})

    def _yaml_extra(self, view: DatasetView) -> dict[str, Any]:
        count = max((len(s.names) for s in view.skeletons.values()), default=0)
        return {"kpt_shape": [count, 3]} if count else {}

    def _line_for(
        self, shape: Shape, index: int, img: ExportImage, report: ExportReport
    ) -> str | None:
        geometry = _geometry(shape, img, report)
        if not isinstance(geometry, Keypoints):
            report.notes.append(Note(img.filename, "Only keypoints go into a pose dataset."))
            return None
        seen = [p for p in geometry.points if p.v > 0] or list(geometry.points)
        left, right = min(p.x for p in seen), max(p.x for p in seen)
        top, bottom = min(p.y for p in seen), max(p.y for p in seen)
        cx, cy = (left + right) / 2, (top + bottom) / 2
        w, h = max(right - left, 1e-6), max(bottom - top, 1e-6)
        box = f"{cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"
        points = " ".join(f"{p.x:.6f} {p.y:.6f} {p.v}" for p in geometry.points)
        return f"{index} {box} {points}"
