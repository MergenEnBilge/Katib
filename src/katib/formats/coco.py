"""COCO format: one JSON file with images, annotations and categories. Boxes and polygons."""

import json
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
from katib.core.geometry import pixels_to_box, pixels_to_polygon, polygon_area
from katib.core.types import Box, GeometryError, Polygon, geometry_bounds, validate_geometry
from katib.formats.common import FormatError, copy_image, unique_names

OUTPUT = "annotations.json"


def _load(path: Path) -> dict[str, Any]:
    file = path
    if path.is_dir():
        candidates = sorted(path.glob("*.json")) + sorted((path / "annotations").glob("*.json"))
        if not candidates:
            raise FormatError("No .json annotation file found in that folder.")
        file = candidates[0]
    try:
        raw: Any = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise FormatError(f"{file.name} is not valid JSON.") from err
    required = ("images", "annotations", "categories")
    if not isinstance(raw, dict) or not all(k in raw for k in required):
        raise FormatError(f"{file.name} needs images, annotations and categories to be COCO.")
    data: dict[str, Any] = raw  # type: ignore[assignment]
    return data


class Coco:
    id = "coco"
    label = "COCO (boxes and polygons)"
    supports = frozenset({"box", "polygon"})

    def detect(self, path: Path) -> bool:
        try:
            _load(path)
        except FormatError:
            return False
        return True

    def read(self, path: Path) -> ParsedDataset:
        data = _load(path)
        categories: dict[int, str] = {int(c["id"]): str(c["name"]) for c in data["categories"]}
        result = ParsedDataset(class_names=list(categories.values()), images=[])
        by_id: dict[int, ImageLabels] = {}
        for img in data["images"]:
            labels = ImageLabels(
                filename=Path(str(img["file_name"])).name,
                width=img.get("width"),
                height=img.get("height"),
            )
            by_id[int(img["id"])] = labels
            result.images.append(labels)
        for ann in data["annotations"]:
            self._read_annotation(ann, categories, by_id, result)
        return result

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
        images_out: list[dict[str, Any]] = []
        anns_out: list[dict[str, Any]] = []
        images = list(view.images())
        dest.mkdir(parents=True, exist_ok=True)
        for image_id, (img, name) in enumerate(
            zip(images, unique_names(images), strict=True), start=1
        ):
            images_out.append(
                {"id": image_id, "file_name": name, "width": img.width, "height": img.height}
            )
            for shape in img.shapes:
                try:
                    item = self._annotation(shape, img.width, img.height)
                except GeometryError as err:
                    report.notes.append(Note(name, str(err)))
                    continue
                item.update(
                    id=len(anns_out) + 1,
                    image_id=image_id,
                    category_id=category_id[shape.class_name],
                    iscrowd=0,
                )
                anns_out.append(item)
            if opts.copy_images and img.source is not None:
                copy_image(img.source, dest / "images", name)
            report.images += 1
        report.shapes = len(anns_out)
        doc = {
            "images": images_out,
            "annotations": anns_out,
            "categories": [{"id": category_id[n], "name": n} for n in names],
        }
        (dest / OUTPUT).write_text(json.dumps(doc, indent=1), encoding="utf-8")
        return report

    def _annotation(self, shape: Shape, width: int, height: int) -> dict[str, Any]:
        geometry = validate_geometry(shape.type, shape.geometry)
        x, y, w, h = geometry_bounds(shape.type, shape.geometry)
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
        assert isinstance(geometry, Box)
        return {"bbox": bbox, "segmentation": [], "area": round(bbox[2] * bbox[3], 2)}
