"""Images: import from a folder or an upload, list with filters, and locate files on disk.

Folder imports index files where they are. Nothing is copied, moved or modified. Every folder
path is resolved and checked against the allowed import roots (ARCHITECTURE.md section 12).
"""

import logging
import os
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from katib import net
from katib.core.split import split_from_names
from katib.db.ids import new_id
from katib.db.models import Annotation, Image
from katib.formats.mask_pngs import mask_files
from katib.services.errors import ImportNotAllowed, InvalidInput, NotFound
from katib.storage.imaging import (
    ALLOWED_SUFFIXES,
    UnreadableImage,
    make_thumbnail,
    sha256_of,
    thumbnail_and_hash,
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
    #: Where a folder chosen through the browser lands. A container cannot browse the computer
    #: running it, so a picked folder arrives as an upload and is written here before it is read
    #: the same way any other connected folder is.
    folder_uploads: LocalStorage
    #: A folder is uploaded one file at a time, so this is a backstop against one that would
    #: never finish, not a real technical ceiling. Set from limits.max_folder_upload_files.
    max_folder_files: int = 20_000


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


def resolved_roots(roots: list[Path]) -> list[Path]:
    """Roots as they exist on disk, for comparing against a resolved path with `inside()`."""
    return [r.resolve() for r in roots]


def container_hint(in_container: bool | None = None) -> str:
    """Why a folder that is plainly on disk can still be invisible to Katib.

    Pass the answer along when the caller already asked `net.in_container()`, since that call
    touches the filesystem and there is no reason to make it twice for one request.
    """
    if not (net.in_container() if in_container is None else in_container):
        return ""
    return (
        " Katib is running in a container, which only sees folders that were mounted with "
        "-v when it started. Add one and restart the container, or upload the pictures instead."
    )


def resolve_path(raw: str, roots: list[Path], *, unrestricted: bool = False) -> Path:
    """Resolve a user-supplied path and require it to sit inside an allowed root.

    `unrestricted` is for the people allowed to browse anywhere, so a path they can pick in the
    browser is also one they can import from.
    """
    if unrestricted:
        try:
            return Path(raw).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as err:
            raise InvalidInput(f"That path does not exist.{container_hint()}") from err
    if not roots:
        raise ImportNotAllowed(
            "No folder is connected yet. An administrator can add one under Settings, then "
            f"Storage, as long as it is already visible to Katib.{container_hint()}"
        )
    try:
        path = Path(raw).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as err:
        raise InvalidInput(f"That path does not exist.{container_hint()}") from err
    if not inside(path, resolved_roots(roots)):
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
        if not inside(path, resolved_roots(ctx.allowed_roots)):
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
    # The checksum reads the file's bytes only, so a duplicate is caught before any decoding.
    digest = sha256_of(source)
    if digest in known:
        return f"duplicate of {known[digest]}"
    image_id = new_id()
    width, height, phash = thumbnail_and_hash(source, ctx.thumbs.path(_thumb_key(image_id)))
    image = Image(
        id=image_id,
        project_id=project_id,
        filename=filename,
        storage_key=storage_key,
        width=width,
        height=height,
        sha256=digest,
        phash=phash,
        position=position,
        split=split,
    )
    session.add(image)
    known[digest] = filename
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
    roots = resolved_roots(ctx.allowed_roots)
    # A segmentation dataset's masks are labels, not more pictures to label.
    masks = mask_files(root)
    files: list[Path] = []
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            path = Path(dirpath) / name
            if path.suffix.lower() in ALLOWED_SUFFIXES and path.resolve() not in masks:
                files.append(path)
    files.sort(key=lambda p: str(p).lower())

    report = ImportReport()
    known = _known_hashes(session, project_id)
    # A rescan meets files it has already added. Leave those alone.
    already_added = _known_keys(session, project_id)
    files = [f for f in files if FILE_PREFIX + str(f.resolve()) not in already_added]
    position = _next_position(session, project_id)
    for i, candidate in enumerate(files, start=1):
        real = candidate.resolve()
        if not inside(real, roots):
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


def missing_in_folder(session: Session, project_id: uuid.UUID, folder: str) -> list[Image]:
    """Pictures read from `folder` whose file is no longer there: deleted, renamed or moved."""
    prefix = FILE_PREFIX + str(Path(folder).resolve()) + os.sep
    rows = session.scalars(
        select(Image).where(Image.project_id == project_id, Image.storage_key.startswith(prefix))
    )
    return [img for img in rows if not Path(img.storage_key[len(FILE_PREFIX) :]).is_file()]


def forget_images(session: Session, ctx: StorageContext, gone: list[Image]) -> int:
    """Take pictures out of the project, with their shapes and comments. Only Katib's own records
    and thumbnails go; whatever file a picture came from is not touched."""
    for image in gone:
        ctx.thumbs.delete(_thumb_key(image.id))
        session.delete(image)
    session.flush()
    return len(gone)


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


#: Files that belong with pictures in an uploaded folder: label files and the sidecar formats
#: connecting a folder already reads. Anything else a folder picker swept up is left out.
FOLDER_UPLOAD_TEXT_SUFFIXES = frozenset({".txt", ".json", ".xml", ".yaml", ".yml"})


def _safe_relative_key(raw: str) -> str | None:
    """The path a browser's folder picker sent, made safe to use as a storage key.

    A browser names every file starting with the folder someone picked, such as
    "MyDataset/images/a.png" for a folder called MyDataset -- so that first part is dropped,
    or a folder connected this way would sit one level below where its own files expect it,
    and never be recognized as the dataset it is.

    None for anything that is not a plain relative path: empty, containing `..`, or a bare
    Windows drive letter. A request can claim whatever name it likes here, browser or not.
    """
    parts = [p for p in re.split(r"[\\/]+", raw) if p not in ("", ".")]
    if not parts or any(p == ".." or re.fullmatch(r"[A-Za-z]:", p) for p in parts):
        return None
    if len(parts) > 1:
        parts = parts[1:]
    return "/".join(parts)


def upload_batch_path(ctx: StorageContext, project_id: uuid.UUID, batch: uuid.UUID) -> Path:
    """Where one folder's uploaded files land, whether or not any have arrived yet."""
    return ctx.folder_uploads.path(f"{project_id}/{batch}")


def count_uploaded_folder_files(
    ctx: StorageContext, project_id: uuid.UUID, batch: uuid.UUID
) -> int:
    root = upload_batch_path(ctx, project_id, batch)
    return sum(1 for p in root.rglob("*") if p.is_file()) if root.is_dir() else 0


def keep_uploaded_folder_file(
    ctx: StorageContext, project_id: uuid.UUID, batch: uuid.UUID, filename: str, data: BinaryIO
) -> bool:
    """Save one file from a folder chosen in the browser, as part of `batch`.

    A folder arrives as many small requests, one per file, rather than one that carries
    everything -- that is what lets the person watch it happen instead of staring at a spinner
    for a folder of any real size.

    True once the file is written. False, quietly, for anything that is not a picture or one of
    the label files usually found beside them -- a folder picker sweeps up a lot of those, and
    reporting each one back would drown out anything worth knowing.
    """
    if count_uploaded_folder_files(ctx, project_id, batch) >= ctx.max_folder_files:
        raise InvalidInput(f"A folder upload is limited to {ctx.max_folder_files:,} files.")
    rel = _safe_relative_key(filename)
    if rel is None:
        return False
    suffix = Path(rel).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES and suffix not in FOLDER_UPLOAD_TEXT_SUFFIXES:
        return False
    try:
        ctx.folder_uploads.put(f"{project_id}/{batch}/{rel}", data, ctx.max_upload_bytes)
    except StorageTooLarge:
        return False
    return True


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
    split: str | None = None,
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
    if split == "none":
        stmt = stmt.where(Image.split.is_(None))
    elif split:
        stmt = stmt.where(Image.split == split)
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
