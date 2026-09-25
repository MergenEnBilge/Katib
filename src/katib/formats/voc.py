"""Pascal VOC: one XML file per image with pixel boxes."""

from collections.abc import Mapping
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement, indent

from defusedxml import ElementTree as SafeXml

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
from katib.core.geometry import obb_to_polygon, pixels_to_box, polygon_to_box
from katib.core.types import Box, GeometryError, Obb, Polygon, validate_geometry
from katib.formats.common import FormatError, copy_image, unique_names


def _xml_files(path: Path) -> list[Path]:
    base = path / "Annotations" if (path / "Annotations").is_dir() else path
    return sorted(base.glob("*.xml"))


def _read_root(file: Path) -> Element | None:
    try:
        root = SafeXml.parse(file).getroot()
    except (SafeXml.ParseError, OSError, ValueError):
        return None
    return root if root is not None and root.tag == "annotation" else None


def _number(node: Element | None, tag: str) -> float | None:
    child = node.find(tag) if node is not None else None
    try:
        return float(child.text) if child is not None and child.text else None
    except ValueError:
        return None


class PascalVoc:
    id = "voc"
    label = "Pascal VOC (boxes)"
    supports = frozenset({"box"})

    def detect(self, path: Path) -> bool:
        if not path.is_dir():
            return False
        files = _xml_files(path)
        return bool(files) and _read_root(files[0]) is not None

    def read(self, path: Path, sizes: Mapping[str, tuple[int, int]] | None = None) -> ParsedDataset:
        if not path.is_dir():
            raise FormatError("Choose the folder that holds the VOC .xml files.")
        files = _xml_files(path)
        if not files:
            raise FormatError("No .xml annotation files found in that folder.")
        result = ParsedDataset(class_names=[], images=[])
        for file in files:
            root = _read_root(file)
            if root is None:
                result.notes.append(Note(file.name, "Not a VOC annotation file."))
                continue
            name = (root.findtext("filename") or file.stem).strip()
            size = root.find("size")
            width = _number(size, "width")
            height = _number(size, "height")
            if not width or not height:
                known = (sizes or {}).get(Path(name).stem.lower())
                width, height = (known[0], known[1]) if known else (None, None)
            labels = ImageLabels(
                filename=Path(name).name,
                width=int(width) if width else None,
                height=int(height) if height else None,
            )
            for number, obj in enumerate(root.findall("object"), start=1):
                self._read_object(obj, labels, result, f"{file.name} object {number}")
            result.images.append(labels)
        return result

    def _read_object(
        self, obj: Element, labels: ImageLabels, result: ParsedDataset, where: str
    ) -> None:
        label = (obj.findtext("name") or "").strip()
        box = obj.find("bndbox")
        xmin, ymin = _number(box, "xmin"), _number(box, "ymin")
        xmax, ymax = _number(box, "xmax"), _number(box, "ymax")
        if not label or None in (xmin, ymin, xmax, ymax):
            result.notes.append(Note(where, "Needs a name and a box."))
            return
        if not labels.width or not labels.height:
            result.notes.append(Note(where, "The image size is not known."))
            return
        assert xmin is not None and ymin is not None and xmax is not None and ymax is not None
        try:
            shape = pixels_to_box(xmin, ymin, xmax - xmin, ymax - ymin, labels.width, labels.height)
        except ValueError:
            result.notes.append(Note(where, "Box is empty or outside the image."))
            return
        if label not in result.class_names:
            result.class_names.append(label)
        labels.shapes.append(Shape(label, "box", shape.model_dump()))

    def write(self, view: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport:
        report = ExportReport()
        images = list(view.images())
        (dest / "Annotations").mkdir(parents=True, exist_ok=True)
        listing: dict[str, list[str]] = {}
        for img, name in zip(images, unique_names(images), strict=True):
            objects = [b for s in img.shapes if (b := self._as_box(s, img, report)) is not None]
            self._write_file(dest / "Annotations" / f"{Path(name).stem}.xml", name, img, objects)
            if opts.copy_images and img.source is not None:
                copy_image(img.source, dest / "JPEGImages", name)
            if img.split:
                listing.setdefault(img.split, []).append(Path(name).stem)
            report.images += 1
            report.shapes += len(objects)
        for split, stems in listing.items():
            sets = dest / "ImageSets" / "Main"
            sets.mkdir(parents=True, exist_ok=True)
            (sets / f"{split}.txt").write_text("\n".join(stems) + "\n", encoding="utf-8")
        return report

    def _as_box(
        self, shape: Shape, img: ExportImage, report: ExportReport
    ) -> tuple[str, Box] | None:
        try:
            geometry = validate_geometry(shape.type, shape.geometry)
        except GeometryError as err:
            report.notes.append(Note(img.filename, str(err)))
            return None
        if isinstance(geometry, Box):
            return shape.class_name, geometry
        if isinstance(geometry, Polygon):
            report.notes.append(Note(img.filename, "Polygon written as its bounding box."))
            return shape.class_name, polygon_to_box(geometry)
        if isinstance(geometry, Obb):
            report.notes.append(Note(img.filename, "Rotated box written as its bounding box."))
            return shape.class_name, polygon_to_box(obb_to_polygon(geometry, img.width, img.height))
        report.notes.append(Note(img.filename, f"A {shape.type} cannot be written in VOC."))
        return None

    def _write_file(
        self, file: Path, name: str, img: ExportImage, objects: list[tuple[str, Box]]
    ) -> None:
        root = Element("annotation")
        SubElement(root, "filename").text = name
        size = SubElement(root, "size")
        SubElement(size, "width").text = str(img.width)
        SubElement(size, "height").text = str(img.height)
        SubElement(size, "depth").text = "3"
        for label, box in objects:
            obj = SubElement(root, "object")
            SubElement(obj, "name").text = label
            SubElement(obj, "difficult").text = "0"
            bndbox = SubElement(obj, "bndbox")
            SubElement(bndbox, "xmin").text = str(round(box.x * img.width))
            SubElement(bndbox, "ymin").text = str(round(box.y * img.height))
            SubElement(bndbox, "xmax").text = str(round((box.x + box.w) * img.width))
            SubElement(bndbox, "ymax").text = str(round((box.y + box.h) * img.height))
        indent(root)
        ElementTree(root).write(file, encoding="utf-8", xml_declaration=True)
