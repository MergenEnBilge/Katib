"""COCO format: one JSON file with images, annotations and categories.

Boxes, polygons and keypoints. Rotated boxes are written as polygons.
"""

import json
import re
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
    SkeletonSpec,
)
from katib.core.geometry import obb_to_polygon, pixels_to_box, pixels_to_polygon, polygon_area
from katib.core.split import split_from_names
from katib.core.types import (
    Box,
    GeometryError,
    Keypoints,
    Obb,
    Polygon,
    geometry_bounds,
    validate_geometry,
)
from katib.formats.common import FormatError, copy_image, unique_names

OUTPUT = "annotations.json"


def _read_file(file: Path) -> dict[str, Any]:
    try:
        raw: Any = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise FormatError(f"{file.name} is not valid JSON.") from err
    required = ("images", "annotations", "categories")
    if not isinstance(raw, dict) or not all(k in raw for k in required):
        raise FormatError(f"{file.name} needs images, annotations and categories to be COCO.")
    data: dict[str, Any] = raw  # type: ignore[assignment]
    return data


def _load(path: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Every COCO file at `path`. A folder may hold one per split, as our own export writes."""
    if not path.is_dir():
        return [(path, _read_file(path))]
    candidates = sorted(path.glob("*.json")) + sorted((path / "annotations").glob("*.json"))
    if not candidates:
        raise FormatError("No .json annotation file found in that folder.")
    found: list[tuple[Path, dict[str, Any]]] = []
    for file in candidates:
        try:
            found.append((file, _read_file(file)))
        except FormatError:
            if len(candidates) == 1:
                raise
    if not found:
        raise FormatError("None of the .json files in that folder are COCO annotations.")
    return found


def _unit(value: float) -> float:
    return min(1.0, max(0.0, value))


class Coco:
    id = "coco"
    label = "COCO (boxes, polygons and keypoints)"
    supports = frozenset({"box", "polygon", "keypoints"})

    def detect(self, path: Path) -> bool:
        try:
            _load(path)
        except FormatError:
            return False
        return True

    def read(self, path: Path, sizes: Mapping[str, tuple[int, int]] | None = None) -> ParsedDataset:
        result = ParsedDataset(class_names=[], images=[])
        for file, data in _load(path):
            self._read_file(file, data, result)
        return result

    def _read_file(self, file: Path, data: dict[str, Any], result: ParsedDataset) -> None:
        # instances_train2017.json and val.json say which split they hold.
        split = split_from_names(re.findall(r"[a-z]+", file.stem.lower()))
        categories: dict[int, str] = {int(c["id"]): str(c["name"]) for c in data["categories"]}
        result.class_names.extend(n for n in categories.values() if n not in result.class_names)
        for category in data["categories"]:
            names = category.get("keypoints")
            if isinstance(names, list) and names:
                edges = [(int(a) - 1, int(b) - 1) for a, b in category.get("skeleton", [])]
                result.skeletons[str(category["name"])] = SkeletonSpec(
                    [str(n) for n in names], edges
                )
        by_id: dict[int, ImageLabels] = {}
        for img in data["images"]:
            labels = ImageLabels(
                filename=Path(str(img["file_name"])).name,
                width=img.get("width"),
                height=img.get("height"),
                split=split,
            )
            by_id[int(img["id"])] = labels
            result.images.append(labels)
        for ann in data["annotations"]:
            self._read_annotation(ann, categories, by_id, result)

    def _read_annotation(
        self,
        ann: dict[str, Any],
        categories: dict[int, str],
        by_id: dict[int, ImageLabels],
        result: ParsedDataset,
    ) -> None:
        where = f"annotation {ann.get('id')}"
        labels = by_id.get(int(ann["image_id"]))
        name = categories.get(int(ann["category_id"]))
        if labels is None or name is None:
            result.notes.append(Note(where, "Refers to an image or category that is not listed."))
            return
        if not labels.width or not labels.height:
            result.notes.append(Note(where, "Image has no width and height."))
            return
        w, h = int(labels.width), int(labels.height)
        seg = ann.get("segmentation")
        if ann.get("iscrowd") or isinstance(seg, dict):
            result.notes.append(Note(where, "Run-length masks are not supported yet."))
            return
        try:
            points = ann.get("keypoints")
            if isinstance(points, list) and any(points):
                marks = [
                    {
                        "x": _unit(points[i] / w),
                        "y": _unit(points[i + 1] / h),
                        "v": int(points[i + 2]),
                    }
                    for i in range(0, len(points) - 2, 3)
                ]
                labels.shapes.append(Shape(name, "keypoints", {"points": marks}))
                return
            if isinstance(seg, list) and seg:
                rings: list[Any] = seg
                for ring in rings:
                    pts = [(ring[i], ring[i + 1]) for i in range(0, len(ring) - 1, 2)]
                    poly = pixels_to_polygon(pts, w, h)
                    labels.shapes.append(Shape(name, "polygon", poly.model_dump()))
                if len(rings) > 1:
                    result.notes.append(Note(where, f"Split into {len(rings)} polygons."))
                return
            x, y, bw, bh = (float(v) for v in ann["bbox"])
            box = pixels_to_box(x, y, bw, bh, w, h)
            labels.shapes.append(Shape(name, "box", box.model_dump()))
        except (ValueError, KeyError, IndexError, TypeError):
            result.notes.append(Note(where, "Shape is empty or outside the image."))

    def write(self, view: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport:
        report = ExportReport()
        names = view.class_names
        category_id = {n: i + 1 for i, n in enumerate(names)}
        images_out: dict[str, list[dict[str, Any]]] = {}
        anns_out: dict[str, list[dict[str, Any]]] = {}
        images = list(view.images())
        dest.mkdir(parents=True, exist_ok=True)
        total = 0
        for image_id, (img, name) in enumerate(
            zip(images, unique_names(images), strict=True), start=1
        ):
            part = img.split or ""
            images_out.setdefault(part, []).append(
                {"id": image_id, "file_name": name, "width": img.width, "height": img.height}
            )
            anns = anns_out.setdefault(part, [])
            for shape in img.shapes:
                try:
                    item = self._annotation(shape, img.width, img.height)
                    if shape.type == "obb":
                        report.notes.append(Note(name, "Rotated box written as a polygon."))
                except GeometryError as err:
                    report.notes.append(Note(name, str(err)))
                    continue
                total += 1
                item.update(
                    id=total,
                    image_id=image_id,
                    category_id=category_id[shape.class_name],
                    iscrowd=0,
                )
                anns.append(item)
            if opts.copy_images and img.source is not None:
                copy_image(img.source, dest / "images" / part, name)
            report.images += 1
        report.shapes = total
        skeletons = view.skeletons
        categories: list[dict[str, Any]] = []
        for n in names:
            category: dict[str, Any] = {"id": category_id[n], "name": n}
            if n in skeletons:
                category["keypoints"] = skeletons[n].names
                category["skeleton"] = [[a + 1, b + 1] for a, b in skeletons[n].edges]
            categories.append(category)
        for part, image_list in images_out.items():
            doc = {
                "images": image_list,
                "annotations": anns_out.get(part, []),
                "categories": categories,
            }
            filename = f"annotations_{part}.json" if part else OUTPUT
            (dest / filename).write_text(json.dumps(doc, indent=1), encoding="utf-8")
        return report

    def _annotation(self, shape: Shape, width: int, height: int) -> dict[str, Any]:
        geometry = validate_geometry(shape.type, shape.geometry)
        x, y, w, h = geometry_bounds(shape.type, shape.geometry, (width, height))
        bbox = [
            round(x * width, 2),
            round(y * height, 2),
            round(w * width, 2),
            round(h * height, 2),
        ]
        if isinstance(geometry, Polygon):
            flat = [round(c, 2) for px, py in geometry.points for c in (px * width, py * height)]
            area = polygon_area(geometry) * width * height
            return {"bbox": bbox, "segmentation": [flat], "area": round(area, 2)}
        if isinstance(geometry, Obb):
            corners = obb_to_polygon(geometry, width, height)
            flat = [round(c, 2) for px, py in corners.points for c in (px * width, py * height)]
            area = geometry.w * width * geometry.h * height
            return {"bbox": bbox, "segmentation": [flat], "area": round(area, 2)}
        if isinstance(geometry, Keypoints):
            flat = [
                value
                for p in geometry.points
                for value in (round(p.x * width, 2), round(p.y * height, 2), p.v)
            ]
            shown = sum(1 for p in geometry.points if p.v > 0)
            return {
                "bbox": bbox,
                "segmentation": [],
                "area": round(bbox[2] * bbox[3], 2),
                "keypoints": flat,
                "num_keypoints": shown,
            }
        if not isinstance(geometry, Box):
            raise GeometryError(f"A {shape.type} cannot be written in COCO.")
        return {"bbox": bbox, "segmentation": [], "area": round(bbox[2] * bbox[3], 2)}
