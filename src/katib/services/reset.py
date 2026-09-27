"""Wiping the data folder back to nothing, the way a freshly installed Katib would find it.

Everything under it is deleted: the database, uploaded pictures, thumbnails, exports, backups and
undo history. A folder you only connected is not touched, since those pictures are yours and were
never copied here.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResetReport:
    files: int
    bytes: int


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
        return ResetReport(0, 0)
    return _count(data_dir)


def factory_reset(data_dir: Path) -> ResetReport:
    """Delete everything in the data folder. Katib rebuilds it from nothing on its next start."""
    if not data_dir.is_dir():
        return ResetReport(0, 0)
    report = _count(data_dir)
    for entry in data_dir.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)
    return report
