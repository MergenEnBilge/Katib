"""Plain data types shared by services and format plugins.

Formats read and write these and never see the database (ARCHITECTURE.md section 13).
Geometry is normalized, class references are names, and image references are filenames.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Shape:
    class_name: str
    type: str  # "box", "polygon", "obb" or "keypoints"
    geometry: dict[str, Any]


@dataclass(frozen=True)
class SkeletonSpec:
    """Landmark names in order, and pairs of positions joined by a line."""

    names: list[str]
    edges: list[tuple[int, int]]


@dataclass
class ImageLabels:
    """Labels for one image. `filename` is how the service matches it to a project image."""

    filename: str
    shapes: list[Shape] = field(default_factory=list[Shape])
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class Note:
    """Something the reader or writer skipped or changed, shown to the person afterward."""

    subject: str
    reason: str


@dataclass
class ParsedDataset:
    class_names: list[str]
    images: list[ImageLabels]
    notes: list[Note] = field(default_factory=list[Note])
    skeletons: dict[str, SkeletonSpec] = field(default_factory=dict[str, SkeletonSpec])


@dataclass(frozen=True)
class ExportImage:
    filename: str
    width: int
    height: int
    shapes: list[Shape]
    source: Path | None = None  # original file, used when copying images into the export
    split: str | None = None  # "train", "val" or "test" when the export is split


class DatasetView(Protocol):
    """Read-only view of what is being exported. Class order is the export index order."""

    @property
    def class_names(self) -> list[str]: ...

    @property
    def skeletons(self) -> dict[str, SkeletonSpec]: ...

    def images(self) -> Iterable[ExportImage]: ...


@dataclass(frozen=True)
class SplitSpec:
    ratios: dict[str, float]
    seed: int = 0
    stratify: bool = False


@dataclass(frozen=True)
class ExportOptions:
    copy_images: bool = False
    split: SplitSpec | None = None


@dataclass
class ExportReport:
    images: int = 0
    shapes: int = 0
    notes: list[Note] = field(default_factory=list[Note])


class Format(Protocol):
    id: str
    label: str
    supports: frozenset[str]

    def detect(self, path: Path) -> bool: ...

    def read(self, path: Path, sizes: Mapping[str, tuple[int, int]] | None = None) -> ParsedDataset:
        """Read a dataset. `sizes` maps lowercase file stems to image pixels, for formats whose
        files do not say how big the picture is."""
        ...

    def write(self, view: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport: ...
