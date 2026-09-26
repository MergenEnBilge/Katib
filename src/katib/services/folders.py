"""Folders on the Katib computer: browsing them and connecting them to projects.

A connected folder is remembered per project, so new photos can be picked up later with a
rescan. Katib only reads inside folders it was allowed to use. Those are the ones named in the
settings file plus every folder someone connected. Who may connect a new one is decided by the
caller: on a single-person install that is anyone, on a shared server it is administrators.
"""

import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from katib.db.models import ProjectFolder
from katib.services.errors import ImportNotAllowed, InvalidInput, NotFound
from katib.services.images import StorageContext, inside, resolve_folder
from katib.storage.imaging import ALLOWED_SUFFIXES

# Folders with more entries than this are counted as "at least this many".
COUNT_LIMIT = 20_000
SHORTCUTS = ("Pictures", "Documents", "Desktop", "Downloads")


@dataclass(frozen=True)
class Place:
    name: str
    path: str


@dataclass(frozen=True)
class Listing:
    path: str | None
    parent: str | None
    places: list[Place]
    folders: list[Place]
    images_here: int
    can_connect: bool


def load_connected(session: Session, ctx: StorageContext) -> None:
    """Allow every folder that was connected in an earlier run. Call once at startup."""
    for (path,) in session.execute(select(ProjectFolder.path).distinct()):
        _allow(ctx, Path(path))


def _allow(ctx: StorageContext, path: Path) -> None:
    if path not in ctx.allowed_roots:
        ctx.allowed_roots.append(path)


def _start_places(ctx: StorageContext, unrestricted: bool) -> list[Place]:
    """Where browsing begins: the home folder and drives, or the folders that were allowed."""
    if not unrestricted:
        return [Place(root.name or str(root), str(root)) for root in ctx.allowed_roots]
    home = Path.home()
    places = [Place("Home", str(home))]
    for name in SHORTCUTS:
        if (home / name).is_dir():
            places.append(Place(name, str(home / name)))
    # Only Windows has drive letters. Checking sys.platform rather than the attribute lets a type
    # checker skip this branch on the platforms where it cannot run.
    if sys.platform == "win32":
        places.extend(Place(drive, drive) for drive in os.listdrives())
    else:
        places.append(Place("Computer", "/"))
    return places


def _count_images(folder: Path) -> int:
    count = 0
    try:
        with os.scandir(folder) as entries:
            for i, entry in enumerate(entries):
                if i >= COUNT_LIMIT:
                    break
                if Path(entry.name).suffix.lower() in ALLOWED_SUFFIXES and entry.is_file():
                    count += 1
    except OSError:
        return 0
    return count


def _subfolders(folder: Path) -> list[Place]:
    found: list[Place] = []
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                if entry.name.startswith("."):
                    continue
                try:
                    if entry.is_dir():
                        found.append(Place(entry.name, str(Path(entry.path))))
                except OSError:
                    continue
    except OSError:
        raise InvalidInput("Katib cannot open that folder.") from None
    return sorted(found, key=lambda p: p.name.lower())


def browse(ctx: StorageContext, raw: str | None, *, unrestricted: bool) -> Listing:
    """List the folders inside `raw`. With no path, list the places browsing can start from.

    `unrestricted` lets the caller look anywhere. Otherwise they stay inside the allowed folders.
    """
    places = _start_places(ctx, unrestricted)
    if not raw:
        return Listing(None, None, places, [], 0, unrestricted)

    try:
        path = Path(raw).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise InvalidInput("That folder does not exist.") from None
    if not path.is_dir():
        raise InvalidInput("That path is not a folder.")
    if not unrestricted and not inside(path, [r.resolve() for r in ctx.allowed_roots]):
        raise ImportNotAllowed("That folder is outside the folders Katib may use.")

    parent = path.parent
    at_top = parent == path or (
        not unrestricted and not inside(parent, [r.resolve() for r in ctx.allowed_roots])
    )
    return Listing(
        path=str(path),
        parent=None if at_top else str(parent),
        places=places,
        folders=_subfolders(path),
        images_here=_count_images(path),
        can_connect=unrestricted or inside(path, [r.resolve() for r in ctx.allowed_roots]),
    )


def connect(
    session: Session,
    project_id: uuid.UUID,
    raw: str,
    ctx: StorageContext,
    *,
    unrestricted: bool,
) -> ProjectFolder:
    """Remember `raw` as one of the project's folders. Connecting the same folder twice is fine."""
    if unrestricted:
        try:
            path = Path(raw).expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            raise InvalidInput("That folder does not exist.") from None
        if not path.is_dir():
            raise InvalidInput("That path is not a folder.")
        _allow(ctx, path)
    else:
        path = resolve_folder(raw, ctx.allowed_roots)

    existing = session.scalar(
        select(ProjectFolder).where(
            ProjectFolder.project_id == project_id, ProjectFolder.path == str(path)
        )
    )
    if existing is not None:
        return existing
    folder = ProjectFolder(project_id=project_id, path=str(path))
    session.add(folder)
    session.flush()
    return folder


def list_connected(session: Session, project_id: uuid.UUID) -> list[ProjectFolder]:
    return list(
        session.scalars(
            select(ProjectFolder)
            .where(ProjectFolder.project_id == project_id)
            .order_by(ProjectFolder.created_at)
        )
    )


def get_connected(session: Session, project_id: uuid.UUID, folder_id: uuid.UUID) -> ProjectFolder:
    folder = session.get(ProjectFolder, folder_id)
    if folder is None or folder.project_id != project_id:
        raise NotFound("That folder is not connected to this project.")
    return folder


def disconnect(session: Session, folder: ProjectFolder) -> None:
    """Stop watching a folder. Images already added stay in the project."""
    session.delete(folder)
