"""Reading image facts and making thumbnails. Originals are opened read-only."""

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
# Pillow identifies pictures by their content, not their name. Naming the formats keeps a file
# called photo.jpg from being opened as something else.
FORMATS = ["JPEG", "PNG", "WEBP", "BMP", "TIFF"]
THUMB_SIZE = 256


class UnreadableImage(ValueError):
    """The file is not an image Katib can read."""


@dataclass(frozen=True)
class ImageInfo:
    width: int
    height: int
    sha256: str
    phash: str


def set_pixel_limit(max_pixels: int) -> None:
    Image.MAX_IMAGE_PIXELS = max_pixels


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _dhash(img: Image.Image) -> str:
    """64-bit difference hash. Near-duplicate images differ in only a few bits."""
    small = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = small.tobytes()
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return f"{bits:016x}"


def read_info(path: Path) -> ImageInfo:
    """Return display dimensions (after EXIF rotation), content hash and perceptual hash."""
    try:
        with Image.open(path, formats=FORMATS) as raw:
            img = ImageOps.exif_transpose(raw)
            width, height = img.size
            phash = _dhash(img)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as err:
        raise UnreadableImage(f"{path.name} is not a readable image.") from err
    return ImageInfo(width, height, sha256_of(path), phash)


def make_thumbnail(src: Path, dest: Path, size: int = THUMB_SIZE) -> None:
    """Write a JPEG thumbnail, EXIF rotation applied. The source file is not modified."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src, formats=FORMATS) as raw:
        img = ImageOps.exif_transpose(raw)
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        img.convert("RGB").save(dest, "JPEG", quality=82)


ORIENTATION_TAG = 0x0112
SIDEWAYS = {5, 6, 7, 8}  # EXIF orientations that turn the picture on its side


def thumbnail_and_hash(src: Path, dest: Path, size: int = THUMB_SIZE) -> tuple[int, int, str]:
    """Write the thumbnail and return the picture's size and perceptual hash, from one decode.

    A JPEG is decoded at reduced size where the format allows it, which is most of the saving on
    a camera photo. The size returned is the full picture's, after EXIF rotation.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(src, formats=FORMATS) as raw:
            width, height = raw.size
            if raw.getexif().get(ORIENTATION_TAG, 1) in SIDEWAYS:
                width, height = height, width
            raw.draft("RGB", (size, size))
            img = ImageOps.exif_transpose(raw)
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            phash = _dhash(img)
            img.convert("RGB").save(dest, "JPEG", quality=82)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as err:
        raise UnreadableImage(f"{src.name} is not a readable image.") from err
    return width, height, phash


def crop_jpeg(
    src: Path, x: float, y: float, w: float, h: float, size: int, pad: float = 0.1
) -> bytes:
    """JPEG of a normalized box plus some context, longest side at most `size` pixels."""
    with Image.open(src, formats=FORMATS) as raw:
        img = ImageOps.exif_transpose(raw)
        iw, ih = img.size
        px, py = w * pad, h * pad
        left = max(0, round((x - px) * iw))
        top = max(0, round((y - py) * ih))
        right = min(iw, round((x + w + px) * iw))
        bottom = min(ih, round((y + h + py) * ih))
        crop = img.crop((left, top, max(right, left + 1), max(bottom, top + 1)))
        crop.thumbnail((size, size), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        crop.convert("RGB").save(out, "JPEG", quality=85)
    return out.getvalue()
