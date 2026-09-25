"""Format registry. Outside packages can add formats through the `katib.formats` entry point."""

from importlib.metadata import entry_points
from pathlib import Path

from katib.core.dataset import Format
from katib.formats.coco import Coco
from katib.formats.common import FormatError
from katib.formats.labelme import LabelMe
from katib.formats.voc import PascalVoc
from katib.formats.yolo import YoloDetect, YoloObb, YoloSegment


def _load() -> dict[str, Format]:
    builtin: tuple[Format, ...] = (
        YoloDetect(),
        YoloSegment(),
        YoloObb(),
        Coco(),
        PascalVoc(),
        LabelMe(),
    )
    found: dict[str, Format] = {f.id: f for f in builtin}
    for entry in entry_points(group="katib.formats"):
        plugin: Format = entry.load()()
        found[plugin.id] = plugin
    return found


REGISTRY = _load()


def get_format(format_id: str) -> Format:
    try:
        return REGISTRY[format_id]
    except KeyError:
        raise FormatError(f"Unknown format {format_id!r}.") from None


def detect_format(path: Path) -> Format:
    """Pick the first format that recognizes `path`.

    The order matters: YOLO segmentation is checked before plain YOLO, because a segmentation
    folder also looks like a detection folder.
    """
    for fmt_id in ("coco", "voc", "labelme", "yolo-segment", "yolo-detect"):
        if REGISTRY[fmt_id].detect(path):
            return REGISTRY[fmt_id]
    for fmt in REGISTRY.values():
        if fmt.detect(path):
            return fmt
    raise FormatError("Katib could not tell what format that is. Choose one from the list.")


__all__ = ["REGISTRY", "FormatError", "detect_format", "get_format"]
