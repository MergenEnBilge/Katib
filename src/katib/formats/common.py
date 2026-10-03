"""Helpers shared by format modules."""

import shutil
from pathlib import Path

from katib.core.dataset import ExportImage


class FormatError(ValueError):
    """The input is not a valid dataset for this format. The message is shown to the person."""


#: Picture files a dataset may hold. Formats only read their names, never their pixels.
IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"})

#: How far below the chosen folder a format looks for its own files, so a dataset whose
#: data.yaml or annotations sit one folder down -- as a downloaded zip often unpacks -- is found.
SEARCH_DEPTH = 2


def find_files(
    root: Path, names: tuple[str, ...] | set[str], depth: int = SEARCH_DEPTH
) -> list[Path]:
    """Files called one of `names` at `root` or up to `depth` folders below it, shallowest first."""
    wanted = {n.lower() for n in names}
    found: list[Path] = []
    level = [root]
    for _ in range(depth + 1):
        following: list[Path] = []
        for folder in level:
            try:
                entries = sorted(folder.iterdir())
            except OSError:
                continue
            for entry in entries:
                if entry.is_file() and entry.name.lower() in wanted:
                    found.append(entry)
                elif entry.is_dir() and not entry.name.startswith("."):
                    following.append(entry)
        level = following
    return found


def parent_folders(file: Path, root: Path) -> tuple[str, ...]:
    """The folders between `root` and `file`, for telling same-named pictures apart."""
    try:
        return file.relative_to(root).parts[:-1]
    except ValueError:
        return ()


def unique_names(images: list[ExportImage]) -> list[str]:
    """Filenames for export. Two images called a.jpg become a.jpg and a_2.jpg."""
    seen: set[str] = set()
    out: list[str] = []
    for img in images:
        name = Path(img.filename).name or "image"
        candidate, n = name, 2
        while candidate.lower() in seen:
            candidate = f"{Path(name).stem}_{n}{Path(name).suffix}"
            n += 1
        seen.add(candidate.lower())
        out.append(candidate)
    return out


def copy_image(source: Path, dest_dir: Path, name: str) -> None:
    """Copy an original into an export. The original is only read."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest_dir / name)
