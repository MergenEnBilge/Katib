"""Segmentation masks as pictures: one PNG per image, where a pixel's value -- or colour -- says
which class covers it. Pascal VOC's SegmentationClass folder is the best known; CVAT and
Roboflow export the same thing with a labelmap.txt naming each colour.

Each class found in a mask becomes one of Katib's own masks on that picture. Value 0 (or black)
is background and 255 marks VOC's "don't care" borders, so neither becomes a shape.

Katib reads these but does not write them: its masks are brush strokes over the whole image, and
the export formats that hold them lose nothing that a picture would keep.
"""

from collections.abc import Mapping
from pathlib import Path

from PIL import Image, ImageChops

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
from katib.formats import masks
from katib.formats.common import IMAGE_SUFFIXES, FormatError, find_files

#: Folders masks are usually kept in. Only these are looked at, so a folder of ordinary PNG
#: photos is never mistaken for masks.
MASK_FOLDERS = {"segmentationclass", "masks", "mask", "segmentation", "segmentation_masks"}
NAME_FILES = ("labelmap.txt", "classes.txt", "class_names.txt", "_classes.txt")
#: What masks often add to the picture's name: a.jpg has a_mask.png.
SUFFIXES = ("_mask", "-mask", "_label", "-label", "_seg", "_segmentation")
BACKGROUND, VOID = 0, 255
#: The order VOC's palette numbers its classes in, when a dataset says nothing else.
VOC_CLASSES = [
    "background", "aeroplane", "bicycle", "bird", "boat", "bottle", "bus", "car", "cat", "chair",
    "cow", "diningtable", "dog", "horse", "motorbike", "person", "pottedplant", "sheep", "sofa",
    "train", "tvmonitor",
]  # fmt: skip


def _mask_folder(path: Path) -> Path | None:
    if path.name.lower() in MASK_FOLDERS:
        return path
    level = [path]
    for _ in range(3):
        following: list[Path] = []
        for folder in level:
            try:
                children = sorted(c for c in folder.iterdir() if c.is_dir())
            except OSError:
                continue
            for child in children:
                if child.name.lower() in MASK_FOLDERS and any(child.glob("*.png")):
                    return child
                following.append(child)
        level = following
    return None


def _names(root: Path) -> tuple[list[str], dict[tuple[int, int, int], str]]:
    """Class names by index, and by colour when a labelmap gives colours."""
    for file in find_files(root, NAME_FILES, depth=2):
        lines = [ln.strip() for ln in file.read_text(encoding="utf-8").splitlines()]
        lines = [ln for ln in lines if ln and not ln.startswith("#")]
        if file.name.lower() == "labelmap.txt":
            colours: dict[tuple[int, int, int], str] = {}
            names: list[str] = []
            for line in lines:
                name, _, rest = line.partition(":")
                rgb = rest.split(":")[0].split(",")
                names.append(name.strip())
                if len(rgb) == 3 and all(p.strip().isdigit() for p in rgb):
                    r, g, b = (int(p) for p in rgb)
                    colours[(r, g, b)] = name.strip()
            return names, colours
        return lines, {}
    return [], {}


def mask_files(root: Path) -> set[Path]:
    """The mask pictures under `root`, so connecting the folder does not add them as pictures
    to label. Only a mask folder whose files pair up with the real pictures by name counts: a
    folder called masks full of photos of masks is photos."""
    folder = _mask_folder(root)
    if folder is None:
        return set()
    found = {p.resolve() for p in folder.rglob("*.png")}
    stems = {_stem(p).lower() for p in found}
    others = {
        p.stem.lower()
        for p in root.rglob("*")
        if p.suffix.lower() in IMAGE_SUFFIXES and p.resolve() not in found
    }
    return found if stems and len(stems & others) * 2 >= len(stems) else set()


def _stem(mask: Path) -> str:
    stem = mask.stem
    for suffix in SUFFIXES:
        if stem.lower().endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def _grid(on: Image.Image) -> dict[str, object] | None:
    """A Katib mask from a black-and-white picture of where one class is."""
    width, height = on.size
    grid_w, grid_h, _ = masks.grid_for(width, height)
    small = on.resize((grid_w, grid_h), Image.Resampling.NEAREST)
    data = small.tobytes()
    if not any(data):
        return None
    rows = [data[y * grid_w : (y + 1) * grid_w] for y in range(grid_h)]
    return {"rle": masks.encode_rows(rows), "size": [grid_w, grid_h]}


class MaskPngs:
    id = "mask-png"
    label = "Segmentation masks (PNG)"
    supports = frozenset({"mask"})
    writes = False

    def detect(self, path: Path) -> bool:
        return path.is_dir() and _mask_folder(path) is not None

    def read(self, path: Path, sizes: Mapping[str, tuple[int, int]] | None = None) -> ParsedDataset:
        folder = _mask_folder(path) if path.is_dir() else None
        if folder is None:
            raise FormatError(
                "No folder of mask pictures found (such as masks/ or SegmentationClass/)."
            )
        names, colours = _names(path)
        result = ParsedDataset(class_names=[], images=[])
        for file in sorted(folder.rglob("*.png")):
            folders = file.relative_to(folder).parts[:-1]
            labels = ImageLabels(
                filename=_stem(file), split=split_from_names(folders), folders=folders
            )
            try:
                with Image.open(file) as picture:
                    picture.load()
                    found = self._classes(picture, names, colours)
            except (OSError, ValueError) as err:
                result.notes.append(Note(file.name, f"Could not read the mask: {err}"))
                continue
            for name, geometry in found:
                if name not in result.class_names:
                    result.class_names.append(name)
                labels.shapes.append(Shape(name, "mask", geometry))
            result.images.append(labels)
        if not result.images:
            raise FormatError("The mask folder has no PNG masks in it.")
        return result

    def _classes(
        self,
        picture: Image.Image,
        names: list[str],
        colours: dict[tuple[int, int, int], str],
    ) -> list[tuple[str, dict[str, object]]]:
        out: list[tuple[str, dict[str, object]]] = []
        if picture.mode in ("P", "L", "I", "I;16"):
            values = picture if picture.mode in ("P", "L") else picture.convert("L")
            index_names = names or (VOC_CLASSES if picture.mode == "P" else [])
            found = sorted(int(v) for _n, v in values.getcolors(65536) or [])  # type: ignore[arg-type]
            for value in found:
                if value in (BACKGROUND, VOID):
                    continue
                name = index_names[value] if value < len(index_names) else f"class {value}"
                geometry = _grid(values.point(lambda p, v=value: 255 if p == v else 0, "L"))
                if geometry is not None:
                    out.append((name, geometry))
            return out
        rgb = picture.convert("RGB")
        bands = rgb.split()
        seen = sorted(
            (int(c[0]), int(c[1]), int(c[2]))  # type: ignore[index]
            for _n, c in rgb.getcolors(1 << 24) or []
        )
        for colour in seen:
            if colour == (0, 0, 0):
                continue
            name = colours.get(colour) or f"colour #{colour[0]:02x}{colour[1]:02x}{colour[2]:02x}"
            if name.lower() in ("background", "_background_"):
                continue
            parts = [
                band.point(lambda p, c=c: 255 if p == c else 0, "L")
                for band, c in zip(bands, colour, strict=True)
            ]
            on = ImageChops.multiply(ImageChops.multiply(parts[0], parts[1]), parts[2])
            geometry = _grid(on)
            if geometry is not None:
                out.append((name, geometry))
        return out

    def write(self, view: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport:
        raise FormatError("Katib reads mask pictures but does not write them. Export as COCO.")
