"""CVAT for images: one annotations.xml holding every picture and its shapes in pixels.

Boxes (rotated ones too), polygons, points and tags. CVAT's subsets (Train, Validation, Test)
become splits.
"""

import math
from collections.abc import Mapping
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement, indent

from defusedxml import ElementTree as SafeXml

from katib.core.dataset import (
    DatasetView,
    ExportOptions,
    ExportReport,
    ImageLabels,
    Note,
    ParsedDataset,
    Shape,
)
from katib.core.geometry import obb_to_polygon, pixels_to_box, pixels_to_polygon
from katib.core.split import split_from_names
from katib.core.types import Box, GeometryError, Keypoints, Obb, Polygon, validate_geometry
from katib.formats.common import FormatError, copy_image, find_files, unique_names

OUTPUT = "annotations.xml"


def _find(path: Path) -> Path | None:
    if path.is_file():
        return path
    for file in find_files(path, (OUTPUT,), depth=1):
        return file
    return None


def _root(file: Path) -> Element | None:
    try:
        root = SafeXml.parse(file).getroot()
    except (SafeXml.ParseError, OSError, ValueError):
        return None
    if root is None or root.tag != "annotations" or root.find("image") is None:
        return None
    return root


def _points(text: str) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for pair in text.split(";"):
        x, _, y = pair.partition(",")
        out.append((float(x), float(y)))
    return out


def _subset(node: Element) -> str | None:
    words = (node.get("subset") or "").lower().split()
    return split_from_names(words)


class Cvat:
    id = "cvat"
    label = "CVAT for images (XML)"
    supports = frozenset({"box", "obb", "polygon", "keypoints", "tag"})

    def detect(self, path: Path) -> bool:
        file = _find(path)
        return file is not None and _root(file) is not None

    def read(self, path: Path, sizes: Mapping[str, tuple[int, int]] | None = None) -> ParsedDataset:
        file = _find(path)
        root = _root(file) if file is not None else None
        if root is None:
            raise FormatError("Choose CVAT's annotations.xml, or the folder that holds it.")
        result = ParsedDataset(class_names=[], images=[])
        for label in root.iter("label"):
            name = (label.findtext("name") or "").strip()
            if name and name not in result.class_names:
                result.class_names.append(name)
        for node in root.findall("image"):
            named = Path((node.get("name") or "").replace("\\", "/"))
            try:
                width, height = int(node.get("width") or 0), int(node.get("height") or 0)
            except ValueError:
                width = height = 0
            labels = ImageLabels(
                filename=named.name,
                width=width or None,
                height=height or None,
                split=_subset(node) or split_from_names(named.parts[:-1]),
                folders=named.parts[:-1],
            )
            for number, item in enumerate(node, start=1):
                self._read_item(item, labels, result, f"{named.name} shape {number}")
            result.images.append(labels)
        return result

    def _read_item(
        self, item: Element, labels: ImageLabels, result: ParsedDataset, where: str
    ) -> None:
        name = (item.get("label") or "").strip()
        if not name:
            return
        if name not in result.class_names:
            result.class_names.append(name)
        if item.tag == "tag":
            labels.shapes.append(Shape(name, "tag", {}))
            return
        if not labels.width or not labels.height:
            result.notes.append(Note(where, "The picture's size is missing."))
            return
        w, h = labels.width, labels.height
        try:
            if item.tag == "box":
                left, top = float(item.get("xtl", "")), float(item.get("ytl", ""))
                right, bottom = float(item.get("xbr", "")), float(item.get("ybr", ""))
                angle = float(item.get("rotation") or 0)
                box = pixels_to_box(left, top, right - left, bottom - top, w, h)
                if angle:
                    obb = Obb(
                        cx=box.x + box.w / 2,
                        cy=box.y + box.h / 2,
                        w=box.w,
                        h=box.h,
                        angle=math.radians(angle),
                    )
                    labels.shapes.append(Shape(name, "obb", obb.model_dump()))
                else:
                    labels.shapes.append(Shape(name, "box", box.model_dump()))
            elif item.tag == "polygon":
                polygon = pixels_to_polygon(_points(item.get("points", "")), w, h)
                labels.shapes.append(Shape(name, "polygon", polygon.model_dump()))
            elif item.tag == "points":
                marks = [
                    {"x": min(max(x / w, 0.0), 1.0), "y": min(max(y / h, 0.0), 1.0), "v": 2}
                    for x, y in _points(item.get("points", ""))
                ]
                labels.shapes.append(Shape(name, "keypoints", {"points": marks}))
            else:
                result.notes.append(Note(where, f"A CVAT {item.tag} is not something Katib draws."))
        except (ValueError, GeometryError):
            result.notes.append(Note(where, "The shape is empty or outside the picture."))

    def write(self, view: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport:
        report = ExportReport()
        dest.mkdir(parents=True, exist_ok=True)
        root = Element("annotations")
        SubElement(root, "version").text = "1.1"
        labels_node = SubElement(SubElement(SubElement(root, "meta"), "task"), "labels")
        for name in view.class_names:
            SubElement(SubElement(labels_node, "label"), "name").text = name
        images = list(view.images())
        subsets = {"train": "Train", "val": "Validation", "test": "Test"}
        for number, (img, name) in enumerate(zip(images, unique_names(images), strict=True)):
            node = SubElement(
                root,
                "image",
                id=str(number),
                name=name,
                width=str(img.width),
                height=str(img.height),
            )
            if img.split:
                node.set("subset", subsets.get(img.split, img.split))
            for shape in img.shapes:
                if self._write_shape(node, shape, img.width, img.height):
                    report.shapes += 1
                else:
                    report.notes.append(Note(name, f"A {shape.type} cannot be written to CVAT."))
            if opts.copy_images and img.source is not None:
                copy_image(img.source, dest / "images", name)
            report.images += 1
        indent(root)
        ElementTree(root).write(dest / OUTPUT, encoding="utf-8", xml_declaration=True)
        return report

    def _write_shape(self, node: Element, shape: Shape, w: int, h: int) -> bool:
        if shape.type == "tag":
            SubElement(node, "tag", label=shape.class_name)
            return True
        try:
            geometry = validate_geometry(shape.type, shape.geometry)
        except GeometryError:
            return False
        if isinstance(geometry, Box):
            SubElement(
                node,
                "box",
                label=shape.class_name,
                xtl=f"{geometry.x * w:.2f}",
                ytl=f"{geometry.y * h:.2f}",
                xbr=f"{(geometry.x + geometry.w) * w:.2f}",
                ybr=f"{(geometry.y + geometry.h) * h:.2f}",
            )
            return True
        if isinstance(geometry, (Polygon, Obb)):
            polygon = geometry if isinstance(geometry, Polygon) else obb_to_polygon(geometry, w, h)
            text = ";".join(f"{x * w:.2f},{y * h:.2f}" for x, y in polygon.points)
            SubElement(node, "polygon", label=shape.class_name, points=text)
            return True
        if isinstance(geometry, Keypoints):
            text = ";".join(f"{p.x * w:.2f},{p.y * h:.2f}" for p in geometry.points)
            SubElement(node, "points", label=shape.class_name, points=text)
            return True
        return False
