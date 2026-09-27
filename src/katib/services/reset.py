"""Wiping the data folder back to nothing, the way a freshly installed Katib would find it.

Everything under it is deleted: the database, uploaded pictures, thumbnails, exports, backups and
undo history. A folder you only connected is not touched, since those pictures are yours and were
never copied here.
"""

import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ResetReport:
    files: int
    bytes: int
    #: Paths that could not be removed, most often because something still had them open. Left
    #: for the caller to log: the answer already went out by the time this runs, so nobody is
    #: waiting on it directly, but it should not be reported as a clean reset if it was not one.
    failed: list[str] = field(default_factory=list[str])


def _count(data_dir: Path) -> ResetReport:
    files = 0
    total = 0
    for path in data_dir.rglob("*"):
        if path.is_file():
            files += 1
            total += path.stat().st_size
    return ResetReport(files, total)


def preview(data_dir: Path) -> ResetReport:
    """What a factory reset would remove, without removing anything."""
    if not data_dir.is_dir():
        return ResetReport(0, 0, [])
    counted = _count(data_dir)
    return ResetReport(counted.files, counted.bytes, [])


def factory_reset(data_dir: Path) -> ResetReport:
    """Delete everything in the data folder. Katib rebuilds it from nothing on its next start."""
    if not data_dir.is_dir():
        return ResetReport(0, 0, [])
    counted = _count(data_dir)
    failed: list[str] = []
    for entry in data_dir.iterdir():
        try:
            if entry.is_dir():
                shutil.rmtree(entry, onexc=lambda _f, path, _e: failed.append(path))
            else:
                entry.unlink()
        except OSError:
            failed.append(str(entry))
    return ResetReport(counted.files, counted.bytes, failed)
