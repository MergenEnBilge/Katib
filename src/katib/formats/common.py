"""Helpers shared by format modules."""

import shutil
from pathlib import Path

from katib.core.dataset import ExportImage


class FormatError(ValueError):
    """The input is not a valid dataset for this format. The message is shown to the person."""


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
