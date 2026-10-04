"""CoNLL: one token per line, its label beside it, a blank line between documents.

This is the oldest and most widely read shape for labelled text. A file looks like this::

    Ada B-person
    works O
    at O
    Katib B-org
    . O

    Grace B-person
    ...

Katib keeps a span as a run of characters, which a file of one token per line cannot hold
exactly, so the words are split the one agreed way (`katib.core.tokens`) and a span that cuts a
token is widened to that token's edges. The export says how many were widened rather than
changing the work in silence.

Reading puts the words back together from the tokens, because a CoNLL file holds no original
text. Spaces may therefore differ from the file the words first came from; the labels do not.
"""

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

FILE = "documents.conll"
SUFFIXES = (".conll", ".conllu", ".iob", ".bio", ".txt")
#: Lines that separate documents in some files rather than only a blank line.
BREAKS = ("-DOCSTART-", "# newdoc")
MAX_COLUMNS = 12


def _rows(line: str) -> list[str]:
    return line.replace("\t", " ").split()


def _looks_like_conll(path: Path) -> bool:
    """Two columns of plain words, with a label that reads like a tag, on most lines."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    tagged = plain = 0
    for line in text.splitlines()[:200]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = _rows(stripped)
        if len(parts) < 2 or len(parts) > MAX_COLUMNS:
            plain += 1
            continue
        last = parts[-1]
        if last == tokens.OUTSIDE or last[:2] in ("B-", "I-", "L-", "U-") or last[:2] == "E-":
            tagged += 1
        else:
            plain += 1
    return tagged > 0 and tagged >= plain


def _find(path: Path) -> Path | None:
    if path.is_file() and path.suffix.lower() in SUFFIXES:
        return path if _looks_like_conll(path) else None
    if not path.is_dir():
        return None
    for name in (FILE, "train.conll", "documents.iob"):
        here = path / name
        if here.is_file() and _looks_like_conll(here):
            return here
    for suffix in (".conll", ".conllu", ".iob", ".bio"):
        for found in sorted(path.glob(f"*{suffix}")):
            if _looks_like_conll(found):
                return found
    return None


class Conll:
    id = "conll"
    label = "CoNLL (one token per line, BIO tags)"
    medium = "text"
    supports = frozenset({"span"})

    def detect(self, path: Path) -> bool:
        return _find(path) is not None

    def read(self, path: Path, sizes: Any = None) -> ParsedDataset:
        del sizes
        found = _find(path)
        if found is None:
            return ParsedDataset([], [])
        names: list[str] = []
        documents: list[ImageLabels] = []
        words: list[str] = []
        tags: list[str] = []
        stem = found.stem or "document"

        def finish() -> None:
            if not words:
                return
            text, found_tokens = tokens.rebuild(words)
            shapes: list[Shape] = []
            for start, end, name in tokens.spans_from_tags(found_tokens, tags):
                if name not in names:
                    names.append(name)
                shapes.append(Shape(name, "span", {"start": start, "end": end}))
            documents.append(
                ImageLabels(f"{stem}-{len(documents) + 1}", shapes, len(text), 1, text=text)
            )
            words.clear()
            tags.clear()

        for line in found.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(BREAKS):
                finish()
                continue
            if stripped.startswith("#"):
                continue
            parts = _rows(stripped)
            if len(parts) < 2:
                continue
            words.append(parts[0])
            tags.append(parts[-1])
        finish()
        return ParsedDataset(names, documents)

    def write(self, view: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport:
        del opts
        report = ExportReport()
        dest.mkdir(parents=True, exist_ok=True)
        blocks: list[str] = []
        widened = 0
        for item in view.images():
            text = item.text
            if text is None:
                report.notes.append(Note(item.filename, "Only text documents go into CoNLL."))
                continue
            spans = [
                (int(s.geometry["start"]), int(s.geometry["end"]), s.class_name)
                for s in item.spans()
            ]
            tagged = tokens.tag(text, spans)
            widened += tagged.widened
            lines = [f"# document = {item.filename}"]
            if item.split:
                lines.append(f"# split = {item.split}")
            lines.extend(
                f"{token.text} {mark}"
                for token, mark in zip(tagged.tokens, tagged.tags, strict=True)
            )
            blocks.append("\n".join(lines))
            report.images += 1
            report.shapes += sum(1 for mark in tagged.tags if mark != tokens.OUTSIDE)
        if widened:
            report.notes.append(
                Note(
                    FILE,
                    f"{widened} span(s) did not line up with a whole word and were stretched to "
                    "fit one. A file of one word per line cannot hold part of a word.",
                )
            )
        (dest / FILE).write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")
        return report
