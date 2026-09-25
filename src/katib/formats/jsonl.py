"""Tags, captions and text: one JSON object per image in metadata.jsonl.

This is the layout Hugging Face's ImageFolder loader reads, so a text dataset made here loads with
one line of code. Every line looks like this:

    {"file_name": "images/train/a.jpg", "width": 640, "height": 480, "split": "train",
     "tags": ["street"], "text": "A red bicycle by a wall.", "texts": ["A red bicycle by a wall."],
     "regions": [{"label": "sign", "type": "box", "geometry": {...}, "text": "STOP"}]}

`text` is the first caption and `texts` holds all of them. Regions are shapes with their own text,
such as a word found in a picture.
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
from katib.core.types import GeometryError, validate_geometry
from katib.formats.common import FormatError, copy_image, unique_names

FILE = "metadata.jsonl"
REGION_TYPES = ("box", "polygon", "obb", "keypoints", "mask")


def _find(path: Path) -> Path | None:
    if path.is_file():
        return path if path.suffix.lower() == ".jsonl" else None
    candidate = path / FILE
    return candidate if candidate.is_file() else None


def _lines(file: Path) -> list[tuple[int, dict[str, Any]]]:
    found: list[tuple[int, dict[str, Any]]] = []
    for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item: Any = json.loads(line)
        except ValueError:
            raise FormatError(f"Line {number} of {file.name} is not valid JSON.") from None
        if not isinstance(item, dict) or "file_name" not in item:
            raise FormatError(f"Line {number} of {file.name} has no file_name.")
        found.append((number, item))  # type: ignore[arg-type]
    return found


class TextLines:
    id = "jsonl"
    label = "Tags and text (JSON Lines, loads in Hugging Face)"
    supports = frozenset({"tag", "text", *REGION_TYPES})

    def detect(self, path: Path) -> bool:
        file = _find(path)
        if file is None:
            return False
        try:
            return bool(_lines(file))
        except (FormatError, OSError):
            return False

    def read(self, path: Path, sizes: Mapping[str, tuple[int, int]] | None = None) -> ParsedDataset:
        file = _find(path)
        if file is None:
            raise FormatError("Choose a folder with metadata.jsonl, or a .jsonl file.")
        result = ParsedDataset(class_names=[], images=[])
        for number, item in _lines(file):
            width, height = item.get("width"), item.get("height")
            split = item.get("split")
            labels = ImageLabels(
                filename=Path(str(item["file_name"]).replace("\\", "/")).name,
                width=int(width) if width else None,
                height=int(height) if height else None,
                split=str(split) if split in ("train", "val", "test") else None,
            )
            self._read_shapes(item, labels, result, f"{file.name} line {number}")
            result.images.append(labels)
        return result

    def _use_class(self, name: str, result: ParsedDataset) -> None:
        if name not in result.class_names:
            result.class_names.append(name)

    def _read_shapes(
        self, item: dict[str, Any], labels: ImageLabels, result: ParsedDataset, where: str
    ) -> None:
        for tag in item.get("tags") or []:
            self._use_class(str(tag), result)
            labels.shapes.append(Shape(str(tag), "tag", {}))
        texts = item.get("texts")
        if not isinstance(texts, list):
            texts = [item["text"]] if item.get("text") else []
        for text in texts:  # type: ignore[reportUnknownVariableType]
            labels.shapes.append(Shape("", "text", {"text": str(text)}))  # type: ignore[reportUnknownArgumentType]
        for region in item.get("regions") or []:
            label = str(region.get("label", "")).strip()
            kind = str(region.get("type", ""))
            try:
                geometry = validate_geometry(kind, region.get("geometry") or {}).model_dump()
            except GeometryError as err:
                result.notes.append(Note(where, str(err)))
                continue
            if not label:
                result.notes.append(Note(where, "A region has no label."))
                continue
            self._use_class(label, result)
            attrs = {"transcription": str(region["text"])} if region.get("text") else {}
            labels.shapes.append(Shape(label, kind, geometry, attrs))

    def write(self, view: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport:
        report = ExportReport()
        images = list(view.images())
        dest.mkdir(parents=True, exist_ok=True)
        rows: list[str] = []
        for img, name in zip(images, unique_names(images), strict=True):
            folder = Path("images") / (img.split or "")
            tags = [s.class_name for s in img.shapes if s.type == "tag"]
            texts = [str(s.geometry.get("text", "")) for s in img.shapes if s.type == "text"]
            texts = [t for t in texts if t]
            regions = [
                {
                    "label": s.class_name,
                    "type": s.type,
                    "geometry": s.geometry,
                    **({"text": s.attrs["transcription"]} if s.attrs.get("transcription") else {}),
                }
                for s in img.shapes
                if s.type in REGION_TYPES
            ]
            row: dict[str, Any] = {
                "file_name": (folder / name).as_posix() if opts.copy_images else name,
                "width": img.width,
                "height": img.height,
                "split": img.split,
                "tags": tags,
                "text": texts[0] if texts else None,
                "texts": texts,
                "regions": regions,
            }
            rows.append(json.dumps(row, ensure_ascii=False))
            if opts.copy_images and img.source is not None:
                copy_image(img.source, dest / folder, name)
            report.images += 1
            report.shapes += len(tags) + len(texts) + len(regions)
        (dest / FILE).write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
        return report
