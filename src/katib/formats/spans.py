"""Text spans: one JSON object per document in documents.jsonl.

Each line holds the words and the runs of characters labelled in them, which is the shape most
text tools read and write:

    {"id": "review-1", "text": "Katib runs on my laptop.", "split": "train",
     "tags": ["positive"], "spans": [{"start": 0, "end": 5, "label": "product",
     "text": "Katib"}]}

`start` is the first character and `end` the one just past the last, so `text[start:end]` is what
was labelled. Offsets count characters, so an accent or an emoji counts as one. The words are in
the file, so an export of a text project is complete on its own.
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
from katib.formats.common import FormatError

FILE = "documents.jsonl"
SPAN_KEYS = ("spans", "entities")
TEXT_KEYS = ("text", "content")


def _find(path: Path) -> Path | None:
    if path.is_file():
        return path if path.suffix.lower() in (".jsonl", ".ndjson") else None
    for name in (FILE, "spans.jsonl", "annotations.jsonl"):
        candidate = path / name
        if candidate.is_file():
            return candidate
    found = sorted(path.glob("*.jsonl"))
    return found[0] if found else None


def _rows(file: Path) -> list[tuple[int, dict[str, Any]]]:
    """Every line that looks like a document: it has words, and spans or tags about them."""
    found: list[tuple[int, dict[str, Any]]] = []
    for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            parsed: Any = json.loads(line)
        except ValueError:
            raise FormatError(f"Line {number} of {file.name} is not valid JSON.") from None
        if not isinstance(parsed, dict):
            raise FormatError(f"Line {number} of {file.name} is not a JSON object.")
        row: dict[str, Any] = parsed
        if not any(isinstance(row.get(key), str) for key in TEXT_KEYS):
            raise FormatError(f"Line {number} of {file.name} has no text.")
        found.append((number, row))
    return found


def _name_for(row: dict[str, Any], number: int, file: Path) -> str:
    for key in ("id", "file_name", "name", "document"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return Path(value.replace("\\", "/")).name
    return f"{file.stem}-{number}"


def _words(row: dict[str, Any]) -> str:
    for key in TEXT_KEYS:
        value = row.get(key)
        if isinstance(value, str):
            return value
    return ""


def _span_list(row: dict[str, Any]) -> list[dict[str, Any]]:
    for key in SPAN_KEYS:
        value = row.get(key)
        if not isinstance(value, list):
            continue
        out: list[dict[str, Any]] = []
        for item in value:  # type: ignore[reportUnknownVariableType]
            if isinstance(item, dict):
                out.append(item)  # type: ignore[reportUnknownArgumentType]
            elif isinstance(item, list | tuple) and len(item) >= 3:  # type: ignore[reportUnknownArgumentType]
                out.append({"start": item[0], "end": item[1], "label": item[2]})  # type: ignore[index]
        if out:
            return out
    return []


class TextSpans:
    id = "jsonl-spans"
    medium = "text"
    label = "Text spans (JSON Lines, words included)"
    supports = frozenset({"span", "tag", "text"})

    def detect(self, path: Path) -> bool:
        file = _find(path)
        if file is None:
            return False
        try:
            rows = _rows(file)
        except (FormatError, OSError):
            return False
        # Words alone are not enough: a file of plain text rows is for adding documents, not for
        # reading labels onto the ones a project already has.
        return any(_span_list(row) or row.get("tags") for _, row in rows)

    def read(self, path: Path, sizes: Mapping[str, tuple[int, int]] | None = None) -> ParsedDataset:
        file = _find(path)
        if file is None:
            raise FormatError("Choose a .jsonl file, or a folder holding documents.jsonl.")
        result = ParsedDataset(class_names=[], images=[])
        for number, row in _rows(file):
            words = _words(row)
            split = row.get("split")
            labels = ImageLabels(
                filename=_name_for(row, number, file),
                width=len(words),
                height=1,
                split=str(split) if split in ("train", "val", "test") else None,
            )
            where = f"{file.name} line {number}"
            self._read_spans(row, words, labels, result, where)
            for tag in row.get("tags") or []:
                name = str(tag).strip()
                if name:
                    self._use_class(name, result)
                    labels.shapes.append(Shape(name, "tag", {}))
            result.images.append(labels)
        return result

    def _use_class(self, name: str, result: ParsedDataset) -> None:
        if name not in result.class_names:
            result.class_names.append(name)

    def _read_spans(
        self,
        row: dict[str, Any],
        words: str,
        labels: ImageLabels,
        result: ParsedDataset,
        where: str,
    ) -> None:
        for span in _span_list(row):
            label = str(span.get("label") or span.get("class") or "").strip()
            if not label:
                result.notes.append(Note(where, "A span has no label."))
                continue
            try:
                start, end = int(span["start"]), int(span["end"])
            except (KeyError, TypeError, ValueError):
                result.notes.append(Note(where, "A span has no start and end."))
                continue
            if words and end > len(words):
                result.notes.append(Note(where, "A span reaches past the end of the words."))
                continue
            try:
                geometry = validate_geometry("span", {"start": start, "end": end}).model_dump()
            except GeometryError as err:
                result.notes.append(Note(where, str(err)))
                continue
            self._use_class(label, result)
            labels.shapes.append(Shape(label, "span", geometry))

    def write(self, view: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport:
        report = ExportReport()
        dest.mkdir(parents=True, exist_ok=True)
        rows: list[str] = []
        for item in view.images():
            if item.kind != "text":
                report.notes.append(
                    Note(item.filename, "Only text documents go into a spans export.")
                )
                continue
            words = ""
            if item.source is not None:
                try:
                    words = item.source.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    report.notes.append(Note(item.filename, "Its words could not be read."))
            spans = [
                {
                    "start": int(s.geometry["start"]),
                    "end": int(s.geometry["end"]),
                    "label": s.class_name,
                    "text": words[int(s.geometry["start"]) : int(s.geometry["end"])],
                }
                for s in item.shapes
                if s.type == "span"
            ]
            tags = [s.class_name for s in item.shapes if s.type == "tag"]
            texts = [str(s.geometry.get("text", "")) for s in item.shapes if s.type == "text"]
            texts = [t for t in texts if t]
            row: dict[str, Any] = {
                "id": item.filename,
                "text": words,
                "split": item.split,
                "spans": spans,
                "tags": tags,
                "notes": texts,
            }
            rows.append(json.dumps(row, ensure_ascii=False))
            report.images += 1
            report.shapes += len(spans) + len(tags) + len(texts)
        (dest / FILE).write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
        return report
