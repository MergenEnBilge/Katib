"""Text documents: the items a project labels when it works with words instead of pictures.

A document is stored next to the uploads as a plain UTF-8 file and indexed in the same table as
pictures, with `kind="text"`. Everything that already works per item -- the queue, locks, review,
splits, comments, the history and undo -- therefore works for documents without knowing about
them. What differs is the shape people draw: a span, which is a run of characters rather than a
place on a picture.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, cast

from sqlalchemy.orm import Session

from katib.core.types import GeometryError, validate_geometry
from katib.db.ids import new_id
from katib.db.models import Annotation, Image
from katib.services import classes
from katib.services.errors import InvalidInput
from katib.services.images import (
    COMMIT_EVERY,
    Skipped,
    StorageContext,
    image_path,
    known_hashes,
    next_position,
)

#: A document longer than this is refused. Long enough for a book chapter, short enough that the
#: browser can show the whole thing at once without the page going slow.
MAX_CHARS = 400_000

#: One document per file.
PLAIN_SUFFIXES = frozenset({".txt", ".md", ".text"})
#: One document per line, with spans if the line carries them.
LINE_SUFFIXES = frozenset({".jsonl", ".ndjson"})
SUFFIXES = PLAIN_SUFFIXES | LINE_SUFFIXES

#: Keys a line may use for its words and its spans. Other tools each pick their own name, and
#: there is no cost to reading all of them.
TEXT_KEYS = ("text", "content", "document", "data")
SPAN_KEYS = ("spans", "entities", "labels", "annotations")


@dataclass
class DocumentReport:
    added: int = 0
    spans: int = 0
    classes_created: list[str] = field(default_factory=list[str])
    skipped: list[Skipped] = field(default_factory=list[Skipped])


def is_document_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUFFIXES


def read_text(image: Image, ctx: StorageContext) -> str:
    """The words of a document. Raises InvalidInput for a picture."""
    if image.kind != "text":
        raise InvalidInput("That item is a picture, not a document.")
    return image_path(image, ctx).read_text(encoding="utf-8", errors="replace")


def add_document(
    session: Session,
    project_id: uuid.UUID,
    filename: str,
    text: str,
    ctx: StorageContext,
    known: dict[str, str] | None = None,
    position: int | None = None,
) -> Image | str:
    """Store `text` as a document in the project. Returns the item, or why it was skipped."""
    # Settle the line endings once, here, where every caller passes through. A file written
    # on Windows arrives with a carriage return on each line, while its words are read back
    # with those collapsed, so storing it as it came would put every span offset out by one
    # character per line before it.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        return "the document is empty"
    if len(text) > MAX_CHARS:
        return f"the document is longer than {MAX_CHARS:,} characters"
    body = text.encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()
    if known is not None and digest in known:
        return f"the same words are already in {known[digest]}"
    key = f"{project_id}/{uuid.uuid4()}.txt"
    ctx.uploads.put(key, BytesIO(body))
    item = Image(
        id=new_id(),
        project_id=project_id,
        filename=filename,
        storage_key=key,
        kind="text",
        # A document has no picture size. Its length goes here so that anything counting or
        # checking an item's extent has a number that means something.
        width=len(text),
        height=1,
        sha256=digest,
        phash=None,
        position=next_position(session, project_id) if position is None else position,
    )
    session.add(item)
    if known is not None:
        known[digest] = filename
    return item


def decode(filename: str, data: bytes) -> str:
    """The words in an uploaded file. Raises InvalidInput for anything that is not UTF-8 text."""
    if Path(filename).suffix.lower() not in SUFFIXES:
        raise InvalidInput(
            "A document file has to be .txt, .md or .jsonl. "
            "A .jsonl file holds one document per line."
        )
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise InvalidInput(
            f"{filename} is not UTF-8 text, so Katib cannot read its words."
        ) from None


def import_file(
    session: Session,
    project_id: uuid.UUID,
    filename: str,
    text: str,
    ctx: StorageContext,
) -> DocumentReport:
    """Read one uploaded file into documents.

    A `.txt` file is one document. A `.jsonl` file is one document per line, and a line may carry
    the spans already found in it, which come in with their classes.
    """
    suffix = Path(filename).suffix.lower()
    report = DocumentReport()
    known = known_hashes(session, project_id)
    position = next_position(session, project_id)
    if suffix in PLAIN_SUFFIXES:
        _one(session, project_id, Path(filename).name, text, [], [], ctx, known, position, report)
        session.commit()
        return report

    stem = Path(filename).stem
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        where = f"{filename} line {number}"
        try:
            parsed: Any = json.loads(line)
        except ValueError:
            report.skipped.append(Skipped(where, "that line is not valid JSON"))
            continue
        if not isinstance(parsed, dict):
            report.skipped.append(Skipped(where, "that line is not a JSON object"))
            continue
        # JSON objects always have string keys, whatever the values turn out to be.
        row = cast(dict[str, Any], parsed)
        words = _words_in(row)
        if words is None:
            report.skipped.append(Skipped(where, "that line has no text"))
            continue
        name = str(row.get("id") or row.get("file_name") or f"{stem}-{number}")
        _one(
            session,
            project_id,
            name,
            words,
            _spans_in(row),
            _tags_in(row),
            ctx,
            known,
            position + report.added,
            report,
        )
        if report.added and report.added % COMMIT_EVERY == 0:
            session.commit()
    session.commit()
    return report


def _one(
    session: Session,
    project_id: uuid.UUID,
    name: str,
    text: str,
    spans: list[dict[str, Any]],
    tags: list[str],
    ctx: StorageContext,
    known: dict[str, str],
    position: int,
    report: DocumentReport,
) -> None:
    made = add_document(session, project_id, name, text, ctx, known, position)
    if isinstance(made, str):
        report.skipped.append(Skipped(name, made))
        return
    report.added += 1
    session.flush()
    _attach_spans(session, project_id, made, text, spans, report)
    for tag in tags:
        cls = _class_for(session, project_id, tag, report)
        session.add(
            Annotation(
                id=new_id(), image_id=made.id, class_id=cls.id, type="tag", geometry={}, attrs={}
            )
        )
        report.spans += 1


def _tags_in(row: dict[str, Any]) -> list[str]:
    """Labels for a whole document, such as the sentiment of a review."""
    value = row.get("tags")
    if not isinstance(value, list):
        return []
    return [str(tag).strip() for tag in value if str(tag).strip()]  # type: ignore[reportUnknownVariableType]


def _class_for(session: Session, project_id: uuid.UUID, name: str, report: DocumentReport) -> Any:
    cls = classes.resolve_class(session, project_id, name)
    if cls is None:
        cls = classes.create_class(session, project_id, name)
        report.classes_created.append(cls.name)
    return cls


def _words_in(row: dict[str, Any]) -> str | None:
    for key in TEXT_KEYS:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _spans_in(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Spans from a line, in any of the shapes the common tools write them in."""
    for key in SPAN_KEYS:
        value = row.get(key)
        if not isinstance(value, list):
            continue
        found: list[dict[str, Any]] = []
        for item in value:  # type: ignore[reportUnknownVariableType]
            if isinstance(item, dict):
                found.append(item)  # type: ignore[reportUnknownArgumentType]
            elif isinstance(item, list | tuple) and len(item) >= 3:  # type: ignore[reportUnknownArgumentType]
                # The spaCy and Prodigy style: [start, end, label].
                found.append({"start": item[0], "end": item[1], "label": item[2]})  # type: ignore[index]
        if found:
            return found
    return []


def _attach_spans(
    session: Session,
    project_id: uuid.UUID,
    item: Image,
    text: str,
    spans: list[dict[str, Any]],
    report: DocumentReport,
) -> None:
    for span in spans:
        label = str(span.get("label") or span.get("class") or span.get("tag") or "").strip()
        if not label:
            report.skipped.append(Skipped(item.filename, "a span has no label"))
            continue
        try:
            start, end = int(span["start"]), int(span["end"])
        except (KeyError, TypeError, ValueError):
            report.skipped.append(Skipped(item.filename, "a span has no start and end"))
            continue
        if end > len(text):
            report.skipped.append(Skipped(item.filename, "a span runs past the end of the words"))
            continue
        try:
            geometry = validate_geometry("span", {"start": start, "end": end}).model_dump()
        except GeometryError as err:
            report.skipped.append(Skipped(item.filename, str(err)))
            continue
        cls = _class_for(session, project_id, label, report)
        session.add(
            Annotation(
                id=new_id(),
                image_id=item.id,
                class_id=cls.id,
                type="span",
                geometry=geometry,
                attrs={},
            )
        )
        report.spans += 1
