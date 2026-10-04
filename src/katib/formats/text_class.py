"""Text and a label for it: the plainest shape there is, as CSV or JSON Lines.

This is what document classification trains on, and what instruction tuning reads. A CSV looks
like this::

    text,label
    "Katib runs on my laptop.",positive

and the JSON Lines version like this::

    {"text": "Katib runs on my laptop.", "label": "positive", "answer": "A short summary."}

A document can carry several labels, in which case they are written separated by a vertical bar,
which is the usual way round a file whose fields are separated by commas. Anything written about
a document goes in `answer`, so a file of prompts and replies reads straight into a fine-tuning
script.

Spans are not in this format. A project that has them should use CoNLL, spaCy, BRAT or Label
Studio instead; the export says so rather than leaving them out in silence.
"""

import csv
import io
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

FILE = "documents.csv"
TEXT_KEYS = ("text", "sentence", "content", "document", "prompt")
LABEL_KEYS = ("label", "labels", "category", "class", "target")
ANSWER_KEYS = ("answer", "completion", "summary", "response", "output")
SEPARATOR = "|"
MAX_SNIFF = 20


def _find(path: Path) -> Path | None:
    if path.is_file() and path.suffix.lower() in (".csv", ".tsv", ".jsonl", ".ndjson"):
        return path
    if not path.is_dir():
        return None
    for name in (FILE, "train.csv", "documents.jsonl", "train.jsonl"):
        here = path / name
        if here.is_file():
            return here
    for pattern in ("*.csv", "*.tsv", "*.jsonl"):
        found = sorted(path.glob(pattern))
        if found:
            return found[0]
    return None


def _rows(path: Path) -> list[dict[str, Any]]:
    """Every row of the file, as plain dictionaries, whichever of the two shapes it is."""
    try:
        body = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    if path.suffix.lower() in (".jsonl", ".ndjson"):
        out: list[dict[str, Any]] = []
        for line in body.splitlines():
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
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    reader = csv.DictReader(io.StringIO(body), delimiter=delimiter)
    return [{k: v for k, v in row.items() if k} for row in reader]


def _pick(row: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        for name, value in row.items():
            if name.strip().lower() == key and isinstance(value, str) and value.strip():
                return value
    return None


def _labels(row: dict[str, Any]) -> list[str]:
    raw = _pick(row, LABEL_KEYS)
    if raw is None:
        for key in LABEL_KEYS:
            value = row.get(key)
            if isinstance(value, list):
                return [str(v) for v in value if str(v).strip()]  # pyright: ignore[reportUnknownVariableType]
        return []
    return [part.strip() for part in raw.split(SEPARATOR) if part.strip()]


class TextClasses:
    id = "text-class"
    label = "Text and a label (CSV or JSON Lines)"
    medium = "text"
    supports = frozenset({"tag", "text"})

    def detect(self, path: Path) -> bool:
        found = _find(path)
        if found is None:
            return False
        rows = _rows(found)[:MAX_SNIFF]
        if not rows:
            return False
        # Words with a label or an answer beside them, and no spans or tokens, which belong to
        # the formats that carry those instead.
        return any(
            _pick(row, TEXT_KEYS) is not None
            and not any(k in row for k in ("spans", "entities", "tokens", "ner_tags"))
            and (_labels(row) or _pick(row, ANSWER_KEYS))
            for row in rows
        )

    def read(self, path: Path, sizes: Any = None) -> ParsedDataset:
        del sizes
        found = _find(path)
        if found is None:
            return ParsedDataset([], [])
        names: list[str] = []
        documents: list[ImageLabels] = []
        stem = found.stem or "document"
        for number, row in enumerate(_rows(found), start=1):
            text = _pick(row, TEXT_KEYS)
            if text is None:
                continue
            name = str(row.get("id") or f"{stem}-{number}")
            shapes: list[Shape] = []
            for label in _labels(row):
                if label not in names:
                    names.append(label)
                shapes.append(Shape(label, "tag", {}))
            answer = _pick(row, ANSWER_KEYS)
            if answer:
                shapes.append(Shape("", "text", {"text": answer}))
            split = row.get("split") if row.get("split") in ("train", "val", "test") else None
            documents.append(
                ImageLabels(
                    name, shapes, len(text), 1, split=str(split) if split else None, text=text
                )
            )
        return ParsedDataset(names, documents)

    def write(self, view: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport:
        del opts
        report = ExportReport()
        dest.mkdir(parents=True, exist_ok=True)
        out = io.StringIO(newline="")
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(["id", "text", "label", "answer", "split"])
        dropped = 0
        for item in view.images():
            text = item.text
            if text is None:
                report.notes.append(Note(item.filename, "Only text documents go into this export."))
                continue
            dropped += len(item.spans()) + len(item.relations())
            tags = item.tags()
            answers = item.captions()
            writer.writerow(
                [
                    item.filename,
                    text,
                    SEPARATOR.join(tags),
                    answers[0] if answers else "",
                    item.split or "",
                ]
            )
            report.images += 1
            report.shapes += len(tags) + (1 if answers else 0)
        if dropped:
            report.notes.append(
                Note(
                    FILE,
                    f"{dropped} span(s) and link(s) were left out. This format holds a label for "
                    "a whole document. Use CoNLL, spaCy, BRAT or Label Studio for spans.",
                )
            )
        (dest / FILE).write_text(out.getvalue(), encoding="utf-8")
        return report
