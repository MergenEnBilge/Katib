"""LabelMe: one JSON file per image with named shapes in pixel coordinates."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

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
from katib.core.geometry import obb_to_polygon, pixels_to_box, pixels_to_polygon
from katib.core.types import Box, GeometryError, Obb, Polygon, validate_geometry
from katib.formats.common import FormatError, copy_image, unique_names


def _load(file: Path) -> dict[str, Any] | None:
    try:
        raw: Any = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(raw, dict) and "shapes" in raw and "imagePath" in raw:
        data: dict[str, Any] = raw  # type: ignore[assignment]
        return data
    return None


class LabelMe:
    id = "labelme"
    label = "LabelMe (boxes and polygons)"
    supports = frozenset({"box", "polygon"})

    def detect(self, path: Path) -> bool:
        if not path.is_dir():
            return False
        return any(_load(f) is not None for f in sorted(path.glob("*.json"))[:5])

    def read(self, path: Path, sizes: Mapping[str, tuple[int, int]] | None = None) -> ParsedDataset:
        if not path.is_dir():
            raise FormatError("Choose the folder that holds the LabelMe .json files.")
        result = ParsedDataset(class_names=[], images=[])
        for file in sorted(path.rglob("*.json")):
            data = _load(file)
            if data is None:
                result.notes.append(Note(file.name, "Not a LabelMe file."))
                continue
            width, height = data.get("imageWidth"), data.get("imageHeight")
            labels = ImageLabels(
                filename=Path(str(data["imagePath"]).replace("\\", "/")).name,
                width=int(width) if width else None,
                height=int(height) if height else None,
            )
            for number, item in enumerate(data["shapes"], start=1):
                self._read_shape(item, labels, result, f"{file.name} shape {number}")
            result.images.append(labels)
        return result

    def _read_shape(
        self, item: dict[str, Any], labels: ImageLabels, result: ParsedDataset, where: str
    ) -> None:
        label = str(item.get("label", "")).strip()
        kind = item.get("shape_type", "polygon")
        if not label:
            result.notes.append(Note(where, "The shape has no label."))
            return
        if not labels.width or not labels.height:
            result.notes.append(Note(where, "The image size is missing."))
            return
        w, h = labels.width, labels.height
        try:
            points = [(float(p[0]), float(p[1])) for p in item["points"]]
            if kind == "rectangle" and len(points) == 2:
                (x1, y1), (x2, y2) = points
                box = pixels_to_box(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1), w, h)
                shape = Shape(label, "box", box.model_dump())
            elif kind == "polygon" and len(points) >= 3:
                shape = Shape(label, "polygon", pixels_to_polygon(points, w, h).model_dump())
            else:
                result.notes.append(Note(where, f"A {kind} shape is not supported."))
                return
        except (KeyError, IndexError, TypeError, ValueError):
            result.notes.append(Note(where, "Shape is empty or outside the image."))
            return
        if label not in result.class_names:
            result.class_names.append(label)
        labels.shapes.append(shape)

    def write(self, view: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport:
        report = ExportReport()
        images = list(view.images())
        for img, name in zip(images, unique_names(images), strict=True):
            folder = dest / (img.split or "")
            folder.mkdir(parents=True, exist_ok=True)
            shapes = [s for shape in img.shapes if (s := self._item(shape, img, report))]
            document = {
                "version": "5.0.0",
                "flags": {},
                "shapes": shapes,
                "imagePath": name,
                "imageData": None,
                "imageHeight": img.height,
                "imageWidth": img.width,
            }
            (folder / f"{Path(name).stem}.json").write_text(
                json.dumps(document, indent=2), encoding="utf-8"
            )
            if opts.copy_images and img.source is not None:
                copy_image(img.source, folder, name)
            report.images += 1
            report.shapes += len(shapes)
        return report

    def _item(self, shape: Shape, img: ExportImage, report: ExportReport) -> dict[str, Any] | None:
        try:
            geometry = validate_geometry(shape.type, shape.geometry)
        except GeometryError as err:
            report.notes.append(Note(img.filename, str(err)))
            return None
        w, h = img.width, img.height
        if isinstance(geometry, Box):
            points = [
                [geometry.x * w, geometry.y * h],
                [(geometry.x + geometry.w) * w, (geometry.y + geometry.h) * h],
            ]
            kind = "rectangle"
        elif isinstance(geometry, (Polygon, Obb)):
            polygon = geometry if isinstance(geometry, Polygon) else obb_to_polygon(geometry, w, h)
            points = [[x * w, y * h] for x, y in polygon.points]
            kind = "polygon"
        else:
            report.notes.append(Note(img.filename, f"A {shape.type} cannot be written in LabelMe."))
            return None
        return {
            "label": shape.class_name,
            "points": [[round(x, 2), round(y, 2)] for x, y in points],
            "group_id": None,
            "shape_type": kind,
            "flags": {},
        }
