"""Buckets a server can read pictures from, and bringing those pictures into a project.

The details are kept in `cloud-sources.json` in the data folder, which is readable only by the
account running Katib, the same as the file holding a database password. A key is never sent back
to a browser: the list says which buckets are set up, not how to open them.

Pictures are not copied into Katib. Each one keeps a note of where it came from, its thumbnail is
made once when it is brought in, and the picture itself is fetched when somebody opens it and kept
in a cache that can be deleted at any time.
"""

import contextlib
import json
import uuid
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from katib.core.split import split_from_names
from katib.db.ids import new_id
from katib.db.models import Image
from katib.services.errors import InvalidInput, NotFound
from katib.services.images import (
    ALLOWED_SUFFIXES,
    CLOUD_PREFIX,
    COMMIT_EVERY,
    Progress,
    Skipped,
    StorageContext,
    known_hashes,
    next_position,
    thumb_key,
)
from katib.storage import cloud
from katib.storage.imaging import UnreadableImage, sha256_of, thumbnail_and_hash

FILE = "cloud-sources.json"
#: A name has to be usable in a storage key and readable in a list.
MAX_NAME = 60


@dataclass
class CloudReport:
    added: int = 0
    skipped: list[Skipped] = field(default_factory=list[Skipped])


def _file(data_dir: Path) -> Path:
    return data_dir / FILE


def load(data_dir: Path) -> list[cloud.Source]:
    """Every bucket set up on this server."""
    try:
        raw = json.loads(_file(data_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(raw, list):
        return []
    found: list[cloud.Source] = []
    for item in raw:  # type: ignore[reportUnknownVariableType]
        if not isinstance(item, dict):
            continue
        try:
            found.append(
                cloud.Source(
                    name=str(item["name"]),  # type: ignore[index]
                    provider="azure" if item.get("provider") == "azure" else "s3",  # type: ignore[union-attr]
                    bucket=str(item["bucket"]),  # type: ignore[index]
                    access_key=str(item.get("access_key", "")),  # type: ignore[union-attr]
                    secret=str(item.get("secret", "")),  # type: ignore[union-attr]
                    region=str(item.get("region", "us-east-1")),  # type: ignore[union-attr]
                    endpoint=str(item.get("endpoint", "")),  # type: ignore[union-attr]
                    prefix=str(item.get("prefix", "")),  # type: ignore[union-attr]
                )
            )
        except (KeyError, TypeError):
            continue
    return found


def save(data_dir: Path, sources: list[cloud.Source]) -> None:
    """Write the list back, readable only by the account running Katib."""
    rows = [
        {
            "name": s.name,
            "provider": s.provider,
            "bucket": s.bucket,
            "access_key": s.access_key,
            "secret": s.secret,
            "region": s.region,
            "endpoint": s.endpoint,
            "prefix": s.prefix,
        }
        for s in sources
    ]
    path = _file(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = path.with_suffix(".tmp")
    scratch.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    with contextlib.suppress(OSError):  # not every filesystem has permissions
        scratch.chmod(0o600)
    scratch.replace(path)


def get(data_dir: Path, name: str) -> cloud.Source:
    for source in load(data_dir):
        if source.name == name:
            return source
    raise NotFound(f"No bucket called {name!r} is set up.")


def put(data_dir: Path, source: cloud.Source) -> int:
    """Add or replace a bucket, after checking the details work. Returns what Katib can see."""
    name = source.name.strip()
    if not name or len(name) > MAX_NAME or "/" in name:
        raise InvalidInput("Give the bucket a short name, without a slash in it.")
    if not source.bucket.strip():
        raise InvalidInput("Which bucket or container should Katib read?")
    if not source.access_key or not source.secret:
        raise InvalidInput("Katib needs a key that can read the bucket.")
    checked = cloud.Source(
        name=name,
        provider=source.provider,
        bucket=source.bucket.strip(),
        access_key=source.access_key.strip(),
        secret=source.secret.strip(),
        region=source.region.strip() or "us-east-1",
        endpoint=source.endpoint.strip(),
        prefix=source.prefix.lstrip("/"),
    )
    try:
        found = cloud.check(checked)
    except cloud.CloudError as err:
        raise InvalidInput(str(err)) from None
    rest = [s for s in load(data_dir) if s.name != name]
    save(data_dir, [*rest, checked])
    return found


def remove(data_dir: Path, name: str) -> None:
    """Forget a bucket. Pictures already in a project keep working only while it is set up."""
    sources = load(data_dir)
    kept = [s for s in sources if s.name != name]
    if len(kept) == len(sources):
        raise NotFound(f"No bucket called {name!r} is set up.")
    save(data_dir, kept)


def key_for(source_name: str, object_key: str) -> str:
    return f"{CLOUD_PREFIX}{source_name}/{object_key}"


def split_key(storage_key: str) -> tuple[str, str]:
    """The source's name and the object's name, out of a stored key."""
    rest = storage_key[len(CLOUD_PREFIX) :]
    name, _, object_key = rest.partition("/")
    return name, object_key


def cached_file(image: Image, ctx: StorageContext, data_dir: Path) -> Path:
    """Where the picture is on this computer, fetching it from the bucket the first time."""
    name, object_key = split_key(image.storage_key)
    suffix = Path(object_key).suffix.lower()
    local = f"{image.id}{suffix}"
    if ctx.cloud_cache.exists(local):
        return ctx.cloud_cache.path(local)
    try:
        body = cloud.fetch(get(data_dir, name), object_key, ctx.max_upload_bytes)
    except cloud.CloudError as err:
        raise NotFound(f"That picture could not be fetched from {name}: {err}") from None
    ctx.cloud_cache.put(local, BytesIO(body))
    return ctx.cloud_cache.path(local)


def import_prefix(
    session: Session,
    project_id: uuid.UUID,
    source_name: str,
    prefix: str,
    ctx: StorageContext,
    data_dir: Path,
    progress: Progress | None = None,
) -> CloudReport:
    """Bring every picture under `prefix` into the project, without copying it into Katib."""
    source = get(data_dir, source_name)
    try:
        objects = cloud.list_objects(source, prefix.lstrip("/") or source.prefix)
    except cloud.CloudError as err:
        raise InvalidInput(str(err)) from None
    pictures = [o for o in objects if Path(o.key).suffix.lower() in ALLOWED_SUFFIXES]
    report = CloudReport()
    if not pictures:
        raise InvalidInput("No pictures were found under that name in the bucket.")

    known = known_hashes(session, project_id)
    # What the project already has, so running it again only brings in what is new.
    already = set(session.scalars(select(Image.storage_key).where(Image.project_id == project_id)))
    position = next_position(session, project_id)
    for done, item in enumerate(pictures, start=1):
        storage_key = key_for(source.name, item.key)
        if storage_key not in already:
            # Counting up from where the project ended, rather than asking the database inside
            # the loop: a query here would hold a write open while progress is being written.
            _one(
                session,
                project_id,
                source,
                item,
                storage_key,
                position + report.added,
                known,
                ctx,
                report,
            )
        if done % COMMIT_EVERY == 0:
            session.commit()
        if progress:
            progress(done / len(pictures))
    session.commit()
    return report


def _one(
    session: Session,
    project_id: uuid.UUID,
    source: cloud.Source,
    item: cloud.CloudObject,
    storage_key: str,
    position: int,
    known: dict[str, str],
    ctx: StorageContext,
    report: CloudReport,
) -> None:
    name = Path(item.key).name
    if item.size > ctx.max_upload_bytes:
        report.skipped.append(Skipped(name, "it is larger than the upload limit"))
        return
    try:
        body = cloud.fetch(source, item.key, ctx.max_upload_bytes)
    except cloud.CloudError as err:
        report.skipped.append(Skipped(name, str(err)))
        return
    image_id = new_id()
    local = f"{image_id}{Path(item.key).suffix.lower()}"
    ctx.cloud_cache.put(local, BytesIO(body))
    stored = ctx.cloud_cache.path(local)
    digest = sha256_of(stored)
    if digest in known:
        ctx.cloud_cache.delete(local)
        report.skipped.append(Skipped(name, f"duplicate of {known[digest]}"))
        return
    try:
        width, height, phash = thumbnail_and_hash(stored, ctx.thumbs.path(thumb_key(image_id)))
    except UnreadableImage as err:
        ctx.cloud_cache.delete(local)
        report.skipped.append(Skipped(name, str(err)))
        return
    folders = tuple(Path(item.key).parent.parts)
    session.add(
        Image(
            id=image_id,
            project_id=project_id,
            filename=name,
            storage_key=storage_key,
            kind="image",
            width=width,
            height=height,
            sha256=digest,
            phash=phash,
            position=position,
            split=split_from_names(list(folders)),
        )
    )
    known[digest] = name
    report.added += 1
