"""Plain data types shared by services and format plugins.

Formats read and write these and never see the database (ARCHITECTURE.md section 13).
Geometry is normalized, class references are names, and image references are filenames.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Shape:
    class_name: str
    type: str  # "box" or "polygon"
    geometry: dict[str, Any]


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


@dataclass(frozen=True)
class ExportImage:
    filename: str
    width: int
    height: int
    shapes: list[Shape]
    source: Path | None = None  # original file, used when copying images into the export


class DatasetView(Protocol):
    """Read-only view of what is being exported. Class order is the export index order."""

    @property
    def class_names(self) -> list[str]: ...

    def images(self) -> Iterable[ExportImage]: ...


@dataclass(frozen=True)
class ExportOptions:
    copy_images: bool = False


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

    def read(self, path: Path) -> ParsedDataset: ...

    def write(self, view: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport: ...
