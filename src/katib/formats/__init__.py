"""Format registry. Outside packages can add formats through the `katib.formats` entry point."""

from importlib.metadata import entry_points
from pathlib import Path

from katib.core.dataset import Format
from katib.formats.coco import Coco
from katib.formats.common import FormatError
from katib.formats.createml import CreateMl
from katib.formats.cvat import Cvat
from katib.formats.folders import ClassFolders
from katib.formats.jsonl import TextLines
from katib.formats.labelme import LabelMe
from katib.formats.mask_pngs import MaskPngs
from katib.formats.spans import TextSpans
from katib.formats.voc import PascalVoc
from katib.formats.yolo import YoloDetect, YoloObb, YoloPose, YoloSegment


def _load() -> dict[str, Format]:
    builtin: tuple[Format, ...] = (
        YoloDetect(),
        YoloSegment(),
        YoloObb(),
        YoloPose(),
        Coco(),
        PascalVoc(),
        LabelMe(),
        Cvat(),
        CreateMl(),
        MaskPngs(),
        ClassFolders(),
        # Before the picture-based lines format: both read .jsonl, and each only claims a file
        # whose lines look like its own.
        TextSpans(),
        TextLines(),
    )
    found: dict[str, Format] = {f.id: f for f in builtin}
    for entry in entry_points(group="katib.formats"):
        plugin: Format = entry.load()()
        found[plugin.id] = plugin
    return found


REGISTRY = _load()

#: Most particular first. A file a format names outright (COCO's JSON, CVAT's XML) beats a folder
#: layout, and among YOLO's flavors the line shapes decide: pose and rotated boxes are told apart
#: by their lines before segmentation, which in turn is checked before plain detection, since
#: every one of them also looks like a detection folder. Class folders come last: a folder of
#: folders is the least particular thing a dataset can be.
DETECT_ORDER = (
    "coco",
    "cvat",
    "createml",
    "voc",
    "labelme",
    # Before YOLO: a classes.txt beside the masks would otherwise make it look like a YOLO set.
    "mask-png",
    "yolo-pose",
    "yolo-obb",
    "yolo-segment",
    "yolo-detect",
    "class-folders",
)


def writes(fmt: Format) -> bool:
    """Whether Katib can export to `fmt`, not only read it."""
    return bool(getattr(fmt, "writes", True))


def medium(fmt: Format) -> str:
    """Whether a format is for pictures or for text. Most are for pictures, so that is the default.

    The shapes a format supports do not settle this on their own: a format for sorting documents
    into categories carries whole-item tags, exactly as one for sorting photographs does.
    """
    return str(getattr(fmt, "medium", "image"))


def get_format(format_id: str) -> Format:
    try:
        return REGISTRY[format_id]
    except KeyError:
        raise FormatError(f"Unknown format {format_id!r}.") from None


UNRECOGNISED = "Katib could not tell what format that is. Choose one from the list."


def detect_format(path: Path) -> Format:
    """Pick the first format that recognizes `path`."""
    for fmt_id in DETECT_ORDER:
        if REGISTRY[fmt_id].detect(path):
            return REGISTRY[fmt_id]
    for fmt_id, fmt in REGISTRY.items():
        if fmt_id not in DETECT_ORDER and fmt.detect(path):
            return fmt
    raise FormatError(UNRECOGNISED)


__all__ = ["DETECT_ORDER", "REGISTRY", "FormatError", "detect_format", "get_format", "writes"]
