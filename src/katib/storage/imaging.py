"""Reading image facts and making thumbnails. Originals are opened read-only."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
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
        with Image.open(path) as raw:
            img = ImageOps.exif_transpose(raw)
            width, height = img.size
            phash = _dhash(img)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as err:
        raise UnreadableImage(f"{path.name} is not a readable image.") from err
    return ImageInfo(width, height, sha256_of(path), phash)


def make_thumbnail(src: Path, dest: Path, size: int = THUMB_SIZE) -> None:
    """Write a JPEG thumbnail, EXIF rotation applied. The source file is not modified."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as raw:
        img = ImageOps.exif_transpose(raw)
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        img.convert("RGB").save(dest, "JPEG", quality=82)
