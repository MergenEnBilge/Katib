"""Backups: one zip with the database, the settings, uploaded pictures and undo history.

Pictures in folders you connected are your own files and are not copied. Thumbnails and exports
are made again when needed, so they are left out too. Restoring is the reverse and never writes
outside the data folder.
"""

import json
import sqlite3
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from sqlalchemy.engine import make_url

from katib.config import SAVED_FILE
from katib.services.errors import InvalidInput

DB_NAME = "katib.db"
MANIFEST = "backup.json"
KEPT_FOLDERS = ("uploads", "operations")
Progress = Callable[[float], None]


@dataclass(frozen=True)
class BackupReport:
    files: int
    bytes: int


def sqlite_file(database_url: str) -> Path:
    """The database file behind a SQLite address. Anything else cannot be backed up this way."""
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite") or not url.database:
        raise InvalidInput(
            "Automatic backups cover the built-in database. "
            "For Postgres, back it up with pg_dump and copy the data folder for uploads."
        )
    return Path(url.database)


def _files(data_dir: Path) -> list[Path]:
    found: list[Path] = []
    for folder in KEPT_FOLDERS:
        base = data_dir / folder
        if base.is_dir():
            found.extend(p for p in sorted(base.rglob("*")) if p.is_file())
    return found


def create(
    data_dir: Path, database_url: str, dest: Path, progress: Progress | None = None
) -> BackupReport:
    """Write a backup zip to `dest`. The database is copied with SQLite's own backup, so it is
    consistent even while people are working."""
    source = sqlite_file(database_url)
    if not source.is_file():
        raise InvalidInput("There is no database to back up yet.")
    files = _files(data_dir)
    total = len(files) + 2
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with tempfile.TemporaryDirectory() as scratch, zipfile.ZipFile(dest, "w") as archive:
        copy = Path(scratch) / DB_NAME
        live, snapshot = sqlite3.connect(source), sqlite3.connect(copy)
        try:
            live.backup(snapshot)
        finally:
            snapshot.close()
            live.close()
        archive.write(copy, DB_NAME, zipfile.ZIP_DEFLATED)
        written += copy.stat().st_size
        settings = data_dir / SAVED_FILE
        if settings.is_file():
            archive.write(settings, SAVED_FILE, zipfile.ZIP_DEFLATED)
        manifest = {
            "katib": version("katib"),
            "created": datetime.now(UTC).isoformat(timespec="seconds"),
            "files": len(files),
        }
        archive.writestr(MANIFEST, json.dumps(manifest, indent=2))
        if progress:
            progress(2 / total)
        for number, path in enumerate(files, start=1):
            name = path.relative_to(data_dir).as_posix()
            # Pictures are already compressed, so storing them is faster and no bigger.
            archive.write(path, name, zipfile.ZIP_STORED)
            written += path.stat().st_size
            if progress:
                progress((number + 2) / total)
    return BackupReport(len(files) + 1, written)


def restore(archive_path: Path, data_dir: Path, replace: bool = False) -> BackupReport:
    """Unpack a backup into the data folder. Refuses to overwrite a database unless told to."""
    if not zipfile.is_zipfile(archive_path):
        raise InvalidInput("That file is not a Katib backup.")
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if DB_NAME not in names or MANIFEST not in names:
            raise InvalidInput("That zip does not look like a Katib backup.")
        root = data_dir.resolve()
        for name in names:
            target = (root / name).resolve()
            if root != target and root not in target.parents:
                raise InvalidInput("That backup holds files outside its folder, so it was refused.")
        existing = root / DB_NAME
        if existing.exists():
            if not replace:
                raise InvalidInput(
                    "This data folder already has a database. Restore into an empty folder, "
                    "or choose to replace it. The current one is kept as katib.db.before-restore."
                )
            existing.replace(root / f"{DB_NAME}.before-restore")
        root.mkdir(parents=True, exist_ok=True)
        archive.extractall(root)
        total = sum(i.file_size for i in archive.infolist())
    return BackupReport(len(names) - 1, total)
