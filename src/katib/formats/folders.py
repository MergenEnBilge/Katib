"""Class per folder, the way ImageNet and most image classification datasets are laid out:
`train/cat/1.jpg`, `train/dog/2.jpg`, `val/cat/3.jpg`. Each picture gets its folder's class as a
tag, and the split comes from the folder above.

Picked out by itself only when there are split folders holding class folders, since plenty of
ordinary photo libraries have folders named after trips or people, and those are not classes.
Without split folders (`cat/1.jpg` straight away) it has to be chosen by hand.
"""

import csv
from collections.abc import Mapping
from pathlib import Path

from katib.core.dataset import (
    DatasetView,
    ExportOptions,
    ExportReport,
    ImageLabels,
    Note,
    ParsedDataset,
    Shape,
)
from katib.core.split import split_from_names
from katib.formats.common import IMAGE_SUFFIXES, FormatError, copy_image, unique_names


def _subfolders(folder: Path) -> list[Path]:
    try:
        return sorted(c for c in folder.iterdir() if c.is_dir() and not c.name.startswith("."))
    except OSError:
        return []


def _pictures(folder: Path) -> list[Path]:
    try:
        return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    except OSError:
        return []


def _class_folders(folder: Path) -> list[Path]:
    return [c for c in _subfolders(folder) if _pictures(c)]


def _split_folders(root: Path) -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for child in _subfolders(root):
        split = split_from_names([child.name])
        if split and len(_class_folders(child)) >= 2:
            found.append((child, split))
    return found


class ClassFolders:
    id = "class-folders"
    label = "Class per folder (image classification)"
    supports = frozenset({"tag"})

    def detect(self, path: Path) -> bool:
        return path.is_dir() and bool(_split_folders(path))

    def read(self, path: Path, sizes: Mapping[str, tuple[int, int]] | None = None) -> ParsedDataset:
        if not path.is_dir():
            raise FormatError("Choose the folder that holds the class folders.")
        groups = _split_folders(path) or [(path, None)]
        result = ParsedDataset(class_names=[], images=[])
        for group, split in groups:
            classes = _class_folders(group)
            if not classes:
                continue
            for folder in classes:
                name = folder.name
                if name not in result.class_names:
                    result.class_names.append(name)
                for picture in _pictures(folder):
                    result.images.append(
                        ImageLabels(
                            filename=picture.name,
                            split=split,
                            folders=(group.name, name) if split else (name,),
                            shapes=[Shape(name, "tag", {})],
                        )
                    )
        if not result.images:
            raise FormatError("No class folders with pictures in them were found there.")
        return result

    def write(self, view: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport:
        """Pictures go into a folder named after their tag. Without copying pictures, there is
        nothing to put in folders, so a labels.csv lists what would go where instead."""
        report = ExportReport()
        dest.mkdir(parents=True, exist_ok=True)
        images = list(view.images())
        rows: list[list[str]] = []
        for img, name in zip(images, unique_names(images), strict=True):
            tags = [s.class_name for s in img.shapes if s.type == "tag"]
            if not tags:
                report.notes.append(Note(name, "Has no tag, so it belongs in no class folder."))
                continue
            if len(tags) > 1:
                report.notes.append(Note(name, f"Has {len(tags)} tags; filed under {tags[0]}."))
            part = img.split or ""
            rows.append([name, tags[0], part])
            if opts.copy_images and img.source is not None:
                copy_image(img.source, dest / part / tags[0], name)
            report.images += 1
            report.shapes += 1
        if not opts.copy_images:
            report.notes.append(
                Note("labels.csv", "Turn on copying pictures to get the class folders themselves.")
            )
        with (dest / "labels.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["image", "class", "split"])
            writer.writerows(rows)
        return report
