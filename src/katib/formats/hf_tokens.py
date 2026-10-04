"""The Hugging Face token-classification shape: a list of words and a label for each.

A line looks like this::

    {"tokens": ["Ada", "works", "at", "Katib", "."],
     "ner_tags": ["B-person", "O", "O", "B-org", "O"]}

`datasets.load_dataset("json", data_files=...)` reads this straight into a token-classification
run, which is what most fine-tuning scripts for named entities expect. A `labels.txt` listing
every tag goes beside it, because the usual scripts want the label set up front.

Tags can be written as numbers instead of names. Katib writes names, which are plainer to read,
and reads either: numbers are looked up in `labels.txt` when one is there.

As with CoNLL, one label per word cannot hold part of a word, so a span that cuts one is widened
to its edges and the export says how many.
"""

import json
from pathlib import Path
from typing import Any

from katib.core import tokens
from katib.core.dataset import (
    DatasetView,
    ExportOptions,
    ExportReport,
    ImageLabels,
    Note,
    ParsedDataset,
    Shape,
)

FILE = "documents.jsonl"
LABELS = "labels.txt"
SUFFIXES = (".jsonl", ".ndjson")
TOKEN_KEYS = ("tokens", "words")
TAG_KEYS = ("ner_tags", "tags", "labels", "ner")
MAX_SNIFF = 20


def _rows(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            out.append(dict(parsed))  # pyright: ignore[reportUnknownArgumentType]
    return out


def _words_of(row: dict[str, Any]) -> list[str] | None:
    for key in TOKEN_KEYS:
        raw = row.get(key)
        if isinstance(raw, list) and all(isinstance(v, str) for v in raw):  # pyright: ignore[reportUnknownVariableType]
            return [str(v) for v in raw]  # pyright: ignore[reportUnknownVariableType]
    return None


def _tags_of(row: dict[str, Any]) -> list[Any] | None:
    for key in TAG_KEYS:
        raw = row.get(key)
        if isinstance(raw, list):
            return list(raw)  # pyright: ignore[reportUnknownArgumentType]
    return None


def _find(path: Path) -> Path | None:
    if path.is_file() and path.suffix.lower() in SUFFIXES:
        return path
    if not path.is_dir():
        return None
    for name in (FILE, "train.jsonl"):
        here = path / name
        if here.is_file():
            return here
    for suffix in SUFFIXES:
        found = sorted(path.glob(f"*{suffix}"))
        if found:
            return found[0]
    return None


def _label_names(path: Path) -> list[str]:
    """The label set beside the file, for a file whose tags are numbers."""
    beside = (path.parent if path.is_file() else path) / LABELS
    if not beside.is_file():
        return []
    try:
        return [
            line.strip()
            for line in beside.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        ]
    except OSError:
        return []


class HuggingFaceTokens:
    id = "hf-tokens"
    label = "Hugging Face token classification (JSON Lines)"
    medium = "text"
    supports = frozenset({"span"})

    def detect(self, path: Path) -> bool:
        found = _find(path)
        if found is None:
            return False
        rows = _rows(found)[:MAX_SNIFF]
        return any(_words_of(row) is not None and _tags_of(row) is not None for row in rows)

    def read(self, path: Path, sizes: Any = None) -> ParsedDataset:
        del sizes
        found = _find(path)
        if found is None:
            return ParsedDataset([], [])
        known = _label_names(found)
        names: list[str] = []
        documents: list[ImageLabels] = []
        notes: list[Note] = []
        stem = found.stem or "document"
        for number, row in enumerate(_rows(found), start=1):
            words = _words_of(row)
            raw_tags = _tags_of(row)
            if words is None or raw_tags is None:
                continue
            name = str(row.get("id") or f"{stem}-{number}")
            if len(raw_tags) != len(words):
                notes.append(Note(name, "It has a different number of words and labels."))
                continue
            marks: list[str] = []
            for tag in raw_tags:
                if isinstance(tag, bool):
                    marks.append(tokens.OUTSIDE)
                elif isinstance(tag, int):
                    marks.append(known[tag] if 0 <= tag < len(known) else tokens.OUTSIDE)
                else:
                    marks.append(str(tag))
            text, found_tokens = tokens.rebuild(words)
            shapes: list[Shape] = []
            for start, end, label in tokens.spans_from_tags(found_tokens, marks):
                if label not in names:
                    names.append(label)
                shapes.append(Shape(label, "span", {"start": start, "end": end}))
            split = row.get("split") if row.get("split") in ("train", "val", "test") else None
            documents.append(
                ImageLabels(
                    name, shapes, len(text), 1, split=str(split) if split else None, text=text
                )
            )
        return ParsedDataset(names, documents, notes)

    def write(self, view: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport:
        del opts
        report = ExportReport()
        dest.mkdir(parents=True, exist_ok=True)
        rows: list[str] = []
        used: list[str] = [tokens.OUTSIDE]
        widened = 0
        for item in view.images():
            text = item.text
            if text is None:
                report.notes.append(
                    Note(item.filename, "Only text documents go into a Hugging Face export.")
                )
                continue
            spans = [
                (int(s.geometry["start"]), int(s.geometry["end"]), s.class_name)
                for s in item.spans()
            ]
            tagged = tokens.tag(text, spans)
            widened += tagged.widened
            for mark in tagged.tags:
                if mark not in used:
                    used.append(mark)
            row: dict[str, Any] = {
                "id": item.filename,
                "tokens": [token.text for token in tagged.tokens],
                "ner_tags": tagged.tags,
            }
            if item.split:
                row["split"] = item.split
            rows.append(json.dumps(row, ensure_ascii=False))
            report.images += 1
            report.shapes += sum(1 for mark in tagged.tags if mark != tokens.OUTSIDE)
        if widened:
            report.notes.append(
                Note(
                    FILE,
                    f"{widened} span(s) did not line up with a whole word and were stretched to "
                    "fit one. One label per word cannot hold part of a word.",
                )
            )
        (dest / FILE).write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
        (dest / LABELS).write_text("\n".join(used) + "\n", encoding="utf-8")
        return report
