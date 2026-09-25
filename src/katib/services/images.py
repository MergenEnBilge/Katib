"""Images: import from a folder or an upload, list with filters, and locate files on disk.

Folder imports index files where they are. Nothing is copied, moved or modified. Every folder
path is resolved and checked against the allowed import roots (ARCHITECTURE.md section 12).
"""

import logging
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from katib.core.split import split_from_names
from katib.db.ids import new_id
from katib.db.models import Annotation, Image
from katib.services.errors import ImportNotAllowed, InvalidInput, NotFound
from katib.storage.imaging import (
    ALLOWED_SUFFIXES,
    UnreadableImage,
    make_thumbnail,
    read_info,
)
from katib.storage.local import LocalStorage, StorageTooLarge

log = logging.getLogger(__name__)

FILE_PREFIX = "file:"
COMMIT_EVERY = 50
MAX_PAGE = 500


@dataclass(frozen=True)
class StorageContext:
    """Where Katib keeps its own files and which folders it may index in place."""

    uploads: LocalStorage
    thumbs: LocalStorage
    allowed_roots: list[Path]
    max_upload_bytes: int
    exports: LocalStorage


@dataclass(frozen=True)
class Skipped:
    name: str
    reason: str


@dataclass
class ImportReport:
    added: int = 0
    skipped: list[Skipped] = field(default_factory=list[Skipped])


Progress = Callable[[float], None]


def inside(path: Path, roots: list[Path]) -> bool:
    """True when `path` is one of `roots` or lives below one."""
    return any(root == path or root in path.parents for root in roots)


def resolve_path(raw: str, roots: list[Path]) -> Path:
    """Resolve a user-supplied path and require it to sit inside an allowed root."""
    if not roots:
        raise ImportNotAllowed(
            "No folder is connected yet. Ask an administrator to connect one, "
            "or add it to storage.allowed_import_roots."
        )
    try:
        path = Path(raw).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as err:
        raise InvalidInput("That path does not exist.") from err
    if not inside(path, [r.resolve() for r in roots]):
        raise ImportNotAllowed("That path is outside the allowed import folders.")
    return path


def resolve_folder(folder: str, roots: list[Path]) -> Path:
    path = resolve_path(folder, roots)
    if not path.is_dir():
        raise InvalidInput("That path is not a folder.")
    return path


def image_path(image: Image, ctx: StorageContext) -> Path:
    """Where the original file for an image lives. Re-checks roots for referenced files."""
    if image.storage_key.startswith(FILE_PREFIX):
        path = Path(image.storage_key[len(FILE_PREFIX) :]).resolve()
        if not inside(path, [r.resolve() for r in ctx.allowed_roots]):
            raise NotFound("That image is no longer in an allowed folder.")
        return path
    return ctx.uploads.path(image.storage_key)


def _thumb_key(image_id: uuid.UUID) -> str:
    return f"{image_id}.jpg"


def thumb_path(image: Image, ctx: StorageContext) -> Path:
    """Return the cached thumbnail, making it on first request if it is missing."""
    dest = ctx.thumbs.path(_thumb_key(image.id))
    if not dest.is_file():
        make_thumbnail(image_path(image, ctx), dest)
    return dest


def _next_position(session: Session, project_id: uuid.UUID) -> int:
    top = session.scalar(select(func.max(Image.position)).where(Image.project_id == project_id))
    return 0 if top is None else top + 1


def _known_keys(session: Session, project_id: uuid.UUID) -> set[str]:
    return set(
        session.scalars(
            select(Image.storage_key).where(
                Image.project_id == project_id, Image.storage_key.startswith(FILE_PREFIX)
            )
        )
    )


def _known_hashes(session: Session, project_id: uuid.UUID) -> dict[str, str]:
    rows = session.execute(
        select(Image.sha256, Image.filename).where(Image.project_id == project_id)
    ).all()
    return {sha: name for sha, name in rows}


def _add_image(
    session: Session,
    project_id: uuid.UUID,
    source: Path,
    filename: str,
    storage_key: str,
    position: int,
    known: dict[str, str],
    ctx: StorageContext,
    split: str | None = None,
) -> Image | str:
    """Read `source`, add a row and a thumbnail. Returns the Image, or a reason it was skipped."""
    info = read_info(source)
    if info.sha256 in known:
        return f"duplicate of {known[info.sha256]}"
    image_id = new_id()
    make_thumbnail(source, ctx.thumbs.path(_thumb_key(image_id)))
    image = Image(
        id=image_id,
        project_id=project_id,
        filename=filename,
        storage_key=storage_key,
        width=info.width,
        height=info.height,
        sha256=info.sha256,
        phash=info.phash,
        position=position,
        split=split,
    )
    session.add(image)
    known[info.sha256] = filename
    return image


def import_folder(
    session: Session,
    project_id: uuid.UUID,
    folder: str,
    ctx: StorageContext,
    progress: Progress | None = None,
) -> ImportReport:
    """Index every supported image under `folder` in place. Commits every few images."""
    root = resolve_folder(folder, ctx.allowed_roots)
    resolved_roots = [r.resolve() for r in ctx.allowed_roots]
    files: list[Path] = []
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            if Path(name).suffix.lower() in ALLOWED_SUFFIXES:
                files.append(Path(dirpath) / name)
    files.sort(key=lambda p: str(p).lower())

    report = ImportReport()
    known = _known_hashes(session, project_id)
    # A rescan meets files it has already added. Leave those alone.
    already_added = _known_keys(session, project_id)
    files = [f for f in files if FILE_PREFIX + str(f.resolve()) not in already_added]
    position = _next_position(session, project_id)
    for i, candidate in enumerate(files, start=1):
        real = candidate.resolve()
        if not inside(real, resolved_roots):
            report.skipped.append(Skipped(candidate.name, "links outside the allowed folders"))
        else:
            try:
                result = _add_image(
                    session,
                    project_id,
                    real,
                    candidate.name,
                    FILE_PREFIX + str(real),
                    position,
                    known,
                    ctx,
                    split_from_names([root.name, *candidate.relative_to(root).parts[:-1]]),
                )
            except UnreadableImage as err:
                report.skipped.append(Skipped(candidate.name, str(err)))
            else:
                if isinstance(result, str):
                    report.skipped.append(Skipped(candidate.name, result))
                else:
                    report.added += 1
                    position += 1
        if i % COMMIT_EVERY == 0:
            session.commit()
        if progress:
            progress(i / len(files))
    session.commit()
    log.info("Folder import added %d images, skipped %d", report.added, len(report.skipped))
    return report


def import_upload(
    session: Session,
    project_id: uuid.UUID,
    filename: str,
    data: BinaryIO,
    ctx: StorageContext,
) -> Image:
    """Store one uploaded file under a generated key and index it."""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise InvalidInput(f"{filename} is not a supported image type.")
    key = f"{project_id}/{uuid.uuid4()}{suffix}"
    try:
        ctx.uploads.put(key, data, ctx.max_upload_bytes)
    except StorageTooLarge as err:
        raise InvalidInput(
            f"Files can be up to {ctx.max_upload_bytes // (1024 * 1024)} MB."
        ) from err
    stored = ctx.uploads.path(key)
    try:
        result = _add_image(
            session,
            project_id,
            stored,
            Path(filename).name,
            key,
            _next_position(session, project_id),
            _known_hashes(session, project_id),
            ctx,
        )
    except UnreadableImage as err:
        ctx.uploads.delete(key)
        raise InvalidInput(str(err)) from err
    if isinstance(result, str):
        ctx.uploads.delete(key)
        raise InvalidInput(f"{Path(filename).name} is a {result}.")
    session.flush()
    return result


def get_image(session: Session, image_id: uuid.UUID) -> Image:
    image = session.get(Image, image_id)
    if image is None:
        raise NotFound("That image does not exist.")
    return image


@dataclass(frozen=True)
class ImageRow:
    image: Image
    annotation_count: int


@dataclass(frozen=True)
class ImagePage:
    rows: list[ImageRow]
    next: uuid.UUID | None


def list_images(
    session: Session,
    project_id: uuid.UUID,
    *,
    status: str | None = None,
    q: str | None = None,
    has_annotations: bool | None = None,
    class_id: uuid.UUID | None = None,
    after: uuid.UUID | None = None,
    limit: int = 100,
) -> ImagePage:
    """Keyset-paginated by (position, id). `after` is the last image id of the previous page."""
    limit = max(1, min(limit, MAX_PAGE))
    count = (
        select(func.count(Annotation.id))
        .where(Annotation.image_id == Image.id)
        .correlate(Image)
        .scalar_subquery()
    )
    stmt = select(Image, count).where(Image.project_id == project_id)
    if status:
        stmt = stmt.where(Image.status == status)
    if q:
        stmt = stmt.where(func.lower(Image.filename).contains(q.lower()))
    if has_annotations is True:
        stmt = stmt.where(count > 0)
    elif has_annotations is False:
        stmt = stmt.where(count == 0)
    if class_id is not None:
        stmt = stmt.where(
            select(Annotation.id)
            .where(Annotation.image_id == Image.id, Annotation.class_id == class_id)
            .exists()
        )
    if after is not None:
        marker = session.get(Image, after)
        if marker is None:
            raise InvalidInput("Unknown page marker.")
        stmt = stmt.where(
            (Image.position > marker.position)
            | ((Image.position == marker.position) & (Image.id > marker.id))
        )
    stmt = stmt.order_by(Image.position, Image.id).limit(limit + 1)
    rows = [ImageRow(img, n) for img, n in session.execute(stmt).all()]
    next_id = rows[limit - 1].image.id if len(rows) > limit else None
    return ImagePage(rows[:limit], next_id)


def set_status(session: Session, image_id: uuid.UUID, status: str) -> Image:
    if status not in {"todo", "in_progress", "done", "approved", "rejected"}:
        raise InvalidInput("Unknown image status.")
    image = get_image(session, image_id)
    image.status = status
    image.version += 1
    session.flush()
    return image
