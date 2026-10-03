"""Apple's CreateML object detection JSON: a list of pictures, each with labelled boxes given by
their center and size in pixels.

Roboflow exports one file per split, train/_annotations.createml.json and so on. The files do
not say how big each picture is, so the pictures must already be in the project.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from katib.core.dataset import (
    DatasetView,
    ExportOptions,
    ExportReport,
    ImageLabels,
    Note,
    ParsedDataset,
    Shape,
)
from katib.core.geometry import pixels_to_box
from katib.core.split import split_from_names
from katib.core.types import Box, GeometryError, validate_geometry
from katib.formats.common import FormatError, copy_image, parent_folders, unique_names

OUTPUT = "annotations.createml.json"


def _load(file: Path) -> list[dict[str, Any]] | None:
    try:
        raw: Any = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, list) or not raw:
        return None
    entries: list[Any] = raw  # type: ignore[assignment]
    first = entries[0]
    if isinstance(first, dict) and "image" in first and "annotations" in first:
        return entries  # type: ignore[return-value]
    return None


def _files(path: Path) -> list[tuple[Path, list[dict[str, Any]]]]:
    if path.is_file():
        found = _load(path)
        return [(path, found)] if found is not None else []
    out: list[tuple[Path, list[dict[str, Any]]]] = []
    for file in sorted(path.glob("*.json")) + sorted(path.glob("*/*.json")):
        found = _load(file)
        if found is not None:
            out.append((file, found))
    return out


class CreateMl:
    id = "createml"
    label = "CreateML (boxes)"
    supports = frozenset({"box"})

    def detect(self, path: Path) -> bool:
        return bool(_files(path))

    def read(self, path: Path, sizes: Mapping[str, tuple[int, int]] | None = None) -> ParsedDataset:
        files = _files(path)
        if not files:
            raise FormatError("No CreateML .json file found there.")
        root = path if path.is_dir() else path.parent
        result = ParsedDataset(class_names=[], images=[])
        for file, entries in files:
            here = parent_folders(file, root)
            split = split_from_names(here) or split_from_names(file.stem.lower().split("_"))
            for entry in entries:
                named = Path(str(entry.get("image", "")).replace("\\", "/"))
                size = (sizes or {}).get(named.stem.lower())
                labels = ImageLabels(
                    filename=named.name,
                    width=size[0] if size else None,
                    height=size[1] if size else None,
                    split=split,
                    folders=here + named.parts[:-1],
                )
                for number, item in enumerate(entry.get("annotations") or [], start=1):
                    where = f"{named.name} box {number}"
                    name = str(item.get("label", "")).strip()
                    if not name:
                        continue
                    if size is None:
                        result.notes.append(
                            Note(where, "Add the pictures first: this format has no sizes.")
                        )
                        continue
                    try:
                        c = item["coordinates"]
                        cx, cy = float(c["x"]), float(c["y"])
                        bw, bh = float(c["width"]), float(c["height"])
                        box = pixels_to_box(cx - bw / 2, cy - bh / 2, bw, bh, size[0], size[1])
                    except (KeyError, TypeError, ValueError):
                        result.notes.append(Note(where, "The box is empty or outside the picture."))
                        continue
                    if name not in result.class_names:
                        result.class_names.append(name)
                    labels.shapes.append(Shape(name, "box", box.model_dump()))
                result.images.append(labels)
        return result

    def write(self, view: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport:
        report = ExportReport()
        dest.mkdir(parents=True, exist_ok=True)
        images = list(view.images())
        by_split: dict[str, list[dict[str, Any]]] = {}
        for img, name in zip(images, unique_names(images), strict=True):
            boxes: list[dict[str, Any]] = []
            for shape in img.shapes:
                try:
                    geometry = validate_geometry(shape.type, shape.geometry)
                except GeometryError:
                    geometry = None
                if not isinstance(geometry, Box):
                    report.notes.append(Note(name, f"A {shape.type} cannot go into CreateML."))
                    continue
                boxes.append(
                    {
                        "label": shape.class_name,
                        "coordinates": {
                            "x": round((geometry.x + geometry.w / 2) * img.width, 2),
                            "y": round((geometry.y + geometry.h / 2) * img.height, 2),
                            "width": round(geometry.w * img.width, 2),
                            "height": round(geometry.h * img.height, 2),
                        },
                    }
                )
            part = img.split or ""
            by_split.setdefault(part, []).append({"image": name, "annotations": boxes})
            if opts.copy_images and img.source is not None:
                copy_image(img.source, dest / part, name)
            report.images += 1
            report.shapes += len(boxes)
        for part, entries in by_split.items():
            folder = dest / part
            folder.mkdir(parents=True, exist_ok=True)
            (folder / OUTPUT).write_text(json.dumps(entries, indent=2), encoding="utf-8")
        return report
