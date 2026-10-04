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
    #: One of the annotation types in `katib.core.types`: a drawn shape, a whole-item tag or
    #: caption, a span of characters, or a relation joining two spans.
    type: str
    geometry: dict[str, Any]
    attrs: dict[str, Any] = field(default_factory=dict[str, Any], hash=False)
    #: Katib's own id for the shape. A relation names the two shapes it joins by these, so a
    #: format that carries relations needs them to match one shape to another. Formats that
    #: write shapes on their own leave it empty.
    id: str = ""


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
    split: str | None = None  # "train", "val" or "test" when the dataset says so
    #: Folders the label or image sat in, inside the dataset ("train/labels", "images/val"). Only
    #: used to tell apart two pictures with the same name, one per split, say.
    folders: tuple[str, ...] = ()
    #: The words of a document, for formats that carry the text alongside its labels. A project
    #: with no document of this name gets one made from these words, so a file of labelled text
    #: can be read into an empty project. None for a picture, whose bytes are never in a label
    #: file.
    text: str | None = None


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
    #: "image" for a picture, "text" for a document, whose words are in `source` and whose
    #: `width` is its length in characters.
    kind: str = "image"

    @property
    def text(self) -> str | None:
        """The words of a document, or None for a picture or a file that cannot be read.

        Every format that writes text needs these, so the reading is done once here rather than
        repeated, slightly differently, in each one.
        """
        if self.kind != "text" or self.source is None:
            return None
        try:
            return self.source.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def spans(self) -> list[Shape]:
        """The spans on a document, in the order they appear in the words."""
        return sorted(
            (s for s in self.shapes if s.type == "span"),
            key=lambda s: (int(s.geometry.get("start", 0)), int(s.geometry.get("end", 0))),
        )

    def relations(self) -> list[Shape]:
        return [s for s in self.shapes if s.type == "relation"]

    def tags(self) -> list[str]:
        return [s.class_name for s in self.shapes if s.type == "tag"]

    def captions(self) -> list[str]:
        written = (str(s.geometry.get("text", "")) for s in self.shapes if s.type == "text")
        return [w for w in written if w]


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
    # Use the splits saved on the images when no new split is asked for.
    use_saved_splits: bool = False


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
