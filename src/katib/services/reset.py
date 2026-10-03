"""Wiping the data folder back to nothing, the way a freshly installed Katib would find it.

Everything under it is deleted: the database, uploaded pictures, thumbnails, exports, backups and
undo history. A folder you only connected is not touched, since those pictures are yours and were
never copied here.
"""

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Belong to the server that is running right now, not to the data: its lock on the folder, the
#: note saying where it answers, and its log, all of them held open while it runs.
KEEP = {"server.lock", "server.json", "logs"}
#: What a reset could not remove, for the fresh server to report once it starts.
LEFTOVERS = "reset-leftovers.json"


@dataclass(frozen=True)
class ResetReport:
    files: int
    bytes: int
    #: Paths that could not be removed, most often because something still had them open. Left
    #: for the caller to log: the answer already went out by the time this runs, so nobody is
    #: waiting on it directly, but it should not be reported as a clean reset if it was not one.
    failed: list[str] = field(default_factory=list[str])


def _entries(data_dir: Path) -> list[Path]:
    return [e for e in data_dir.iterdir() if e.name not in KEEP]


def _count(data_dir: Path) -> ResetReport:
    files = 0
    total = 0
    for entry in _entries(data_dir):
        for path in [entry, *entry.rglob("*")] if entry.is_dir() else [entry]:
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
    for entry in _entries(data_dir):
        try:
            if entry.is_dir():
                shutil.rmtree(entry, onexc=lambda _f, path, _e: failed.append(path))
            else:
                entry.unlink()
        except OSError:
            failed.append(str(entry))
    if failed:
        (data_dir / LEFTOVERS).write_text(json.dumps(failed, indent=2), encoding="utf-8")
    return ResetReport(counted.files, counted.bytes, failed)


def leftovers(data_dir: Path) -> list[str]:
    """What the last factory reset could not remove, until someone has seen it."""
    try:
        found: Any = json.loads((data_dir / LEFTOVERS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [str(p) for p in found] if isinstance(found, list) else []  # type: ignore[misc]


def forget_leftovers(data_dir: Path) -> None:
    (data_dir / LEFTOVERS).unlink(missing_ok=True)
