"""LabelMe: one JSON file per image with named shapes in pixel coordinates.

Rectangles and polygons come in as themselves, circles as polygons and single points as one-point
keypoints. The files may sit in split folders (train/, val/) and keep that split.
"""

import json
import math
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
from katib.core.split import split_from_names
from katib.core.types import Box, GeometryError, Obb, Polygon, validate_geometry
from katib.formats.common import FormatError, copy_image, parent_folders, unique_names

#: How many .json files to open before deciding a folder is not LabelMe.
DETECT_SAMPLE = 10
#: Corners of the polygon a circle becomes.
CIRCLE_SIDES = 32


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
        # Files may sit in split folders rather than at the top. Stop early: a big photo library
        # with a stray .json in it should not have every file opened.
        for number, file in enumerate(path.rglob("*.json")):
            if number >= DETECT_SAMPLE:
                return False
            if _load(file) is not None:
                return True
        return False

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
            image_path = Path(str(data["imagePath"]).replace("\\", "/"))
            folders = parent_folders(file, path) + tuple(
                part for part in image_path.parts[:-1] if part not in ("..", ".")
            )
            labels = ImageLabels(
                filename=image_path.name,
                width=int(width) if width else None,
                height=int(height) if height else None,
                split=split_from_names(folders),
                folders=folders,
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
            elif kind == "circle" and len(points) == 2:
                (cx, cy), (ex, ey) = points
                r = math.hypot(ex - cx, ey - cy)
                ring = [
                    (
                        cx + r * math.cos(2 * math.pi * i / CIRCLE_SIDES),
                        cy + r * math.sin(2 * math.pi * i / CIRCLE_SIDES),
                    )
                    for i in range(CIRCLE_SIDES)
                ]
                ring = [(min(max(x, 0.0), w), min(max(y, 0.0), h)) for x, y in ring]
                shape = Shape(label, "polygon", pixels_to_polygon(ring, w, h).model_dump())
            elif kind == "point" and len(points) == 1:
                (x, y) = points[0]
                mark = {"x": min(max(x / w, 0.0), 1.0), "y": min(max(y / h, 0.0), 1.0), "v": 2}
                shape = Shape(label, "keypoints", {"points": [mark]})
            elif kind in ("line", "linestrip"):
                result.notes.append(
                    Note(where, "Katib has no line shape, so this line was left out.")
                )
                return
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
