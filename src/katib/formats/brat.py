"""BRAT standoff: the words in a `.txt` file and the labels beside it in a `.ann` file.

For every `review.txt` there is a `review.ann` holding lines like these::

    T1	person 0 3	Ada
    T2	org 13 18	Katib
    R1	works_for Arg1:T1 Arg2:T2

`T` lines are spans, with character offsets and the words they cover. `R` lines join two of them,
which makes this the plainest format that carries relations as well as spans. It is the usual
choice in biomedical and academic work, and many annotation tools read it.

The words stay in their own file, so nothing about the text is changed by exporting. A class name
with a space in it is written with an underscore instead, because the file is split on spaces,
and read back the same way.
"""

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

MAX_FILES = 20_000


def _pairs(path: Path) -> list[tuple[Path, Path]]:
    """Every `.ann` file and the `.txt` beside it."""
    if path.is_file() and path.suffix.lower() == ".ann":
        words = path.with_suffix(".txt")
        return [(path, words)] if words.is_file() else []
    if not path.is_dir():
        return []
    out: list[tuple[Path, Path]] = []
    for found in sorted(path.rglob("*.ann"))[:MAX_FILES]:
        words = found.with_suffix(".txt")
        if words.is_file():
            out.append((found, words))
    return out


def _label(name: str) -> str:
    return name.replace("_", " ") if " " not in name else name


class Brat:
    id = "brat"
    label = "BRAT standoff (.txt with .ann, carries relations)"
    medium = "text"
    supports = frozenset({"span", "relation"})

    def detect(self, path: Path) -> bool:
        return bool(_pairs(path))

    def read(self, path: Path, sizes: Any = None) -> ParsedDataset:
        del sizes
        names: list[str] = []
        documents: list[ImageLabels] = []
        notes: list[Note] = []
        for ann, words_file in _pairs(path):
            try:
                text = words_file.read_text(encoding="utf-8", errors="replace")
                lines = ann.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                notes.append(Note(ann.name, "It could not be read."))
                continue
            shapes: list[Shape] = []
            # BRAT names each span T1, T2 and so on, and a relation points at those names, so
            # the ids have to be kept while the file is read to join the two up afterward.
            marks: dict[str, str] = {}
            links: list[tuple[str, str, str]] = []
            for line in lines:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 2 or not parts[0]:
                    continue
                mark, body = parts[0], parts[1]
                if mark.startswith("T"):
                    bits = body.split()
                    if len(bits) < 3:
                        continue
                    label, start, end = bits[0], bits[1], bits[-1]
                    try:
                        begin, finish = int(start), int(end)
                    except ValueError:
                        continue
                    if begin < 0 or finish > len(text) or finish <= begin:
                        notes.append(Note(words_file.name, f"A {label} span did not fit."))
                        continue
                    name = _label(label)
                    if name not in names:
                        names.append(name)
                    made = f"{ann.stem}-{mark}"
                    marks[mark] = made
                    shapes.append(Shape(name, "span", {"start": begin, "end": finish}, id=made))
                elif mark.startswith("R"):
                    bits = body.split()
                    if len(bits) < 3:
                        continue
                    label = bits[0]
                    ends = {
                        key.lower(): value
                        for key, _, value in (bit.partition(":") for bit in bits[1:])
                    }
                    first, second = ends.get("arg1"), ends.get("arg2")
                    if first and second:
                        links.append((_label(label), first, second))
            for label, first, second in links:
                start_id, end_id = marks.get(first), marks.get(second)
                if start_id is None or end_id is None:
                    notes.append(Note(words_file.name, f"A {label} link pointed at nothing."))
                    continue
                if label not in names:
                    names.append(label)
                shapes.append(Shape(label, "relation", {"from_id": start_id, "to_id": end_id}))
            documents.append(ImageLabels(words_file.name, shapes, len(text), 1, text=text))
        return ParsedDataset(names, documents, notes)

    def write(self, view: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport:
        del opts
        report = ExportReport()
        dest.mkdir(parents=True, exist_ok=True)
        for item in view.images():
            text = item.text
            if text is None:
                report.notes.append(Note(item.filename, "Only text documents go into BRAT."))
                continue
            stem = Path(item.filename).stem or "document"
            spans = item.spans()
            marks: dict[str, str] = {}
            lines: list[str] = []
            for number, span in enumerate(spans, start=1):
                start, end = int(span.geometry["start"]), int(span.geometry["end"])
                mark = f"T{number}"
                if span.id:
                    marks[span.id] = mark
                label = span.class_name.replace(" ", "_")
                # The words come last on the line, with any newline in them flattened: a span is
                # one line in this format.
                quoted = text[start:end].replace("\n", " ")
                lines.append(f"{mark}\t{label} {start} {end}\t{quoted}")
            number = 0
            for link in item.relations():
                first = marks.get(str(link.geometry.get("from_id", "")))
                second = marks.get(str(link.geometry.get("to_id", "")))
                if first is None or second is None:
                    report.notes.append(
                        Note(item.filename, "A link joined a span that is not in this export.")
                    )
                    continue
                number += 1
                label = link.class_name.replace(" ", "_")
                lines.append(f"R{number}\t{label} Arg1:{first} Arg2:{second}")
            (dest / f"{stem}.txt").write_text(text, encoding="utf-8")
            (dest / f"{stem}.ann").write_text(
                "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
            )
            report.images += 1
            report.shapes += len(lines)
        return report
