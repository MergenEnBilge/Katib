"""Rebuild every icon from brand/logo.png and brand/logo.svg.

python scripts/apply_brand.py                 use the logo files in brand/
python scripts/apply_brand.py --placeholder   write a placeholder logo.png first
"""

import argparse
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "brand"
GREEN = (31, 122, 76, 255)


def placeholder(size: int = 1024) -> Image.Image:
    """The stand-in logo: a green tile with a white K."""
    unit = size / 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(14 * unit), fill=GREEN)
    draw.rectangle([22 * unit, 16 * unit, 28 * unit, 48 * unit], fill="white")
    waist = (34 * unit, 34 * unit)
    draw.polygon(
        [(28 * unit, 33 * unit), (40 * unit, 16 * unit), (48 * unit, 16 * unit), waist], "white"
    )
    draw.polygon(
        [waist, (48 * unit, 48 * unit), (40 * unit, 48 * unit), (28 * unit, 33 * unit)], "white"
    )
    return image


def padded(
    logo: Image.Image, size: int, share: float, background: tuple[int, int, int, int]
) -> Image.Image:
    """The logo centered on a solid tile, for icons the system crops (maskable, adaptive)."""
    tile = Image.new("RGBA", (size, size), background)
    inner = int(size * share)
    small = logo.resize((inner, inner), Image.Resampling.LANCZOS)
    tile.alpha_composite(small, ((size - inner) // 2, (size - inner) // 2))
    return tile


def save(image: Image.Image, path: Path, size: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = image.resize((size, size), Image.Resampling.LANCZOS) if size else image
    out.save(path)
    print("wrote", path.relative_to(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--placeholder", action="store_true", help="write a placeholder logo.png")
    args = parser.parse_args()

    source = BRAND / "logo.png"
    if args.placeholder:
        save(placeholder(), source)
    if not source.is_file():
        print("brand/logo.png is missing. Add yours, or pass --placeholder.", file=sys.stderr)
        return 1

    logo = Image.open(source).convert("RGBA")
    if logo.width != logo.height or logo.width < 512:
        print("brand/logo.png must be square and at least 512 pixels wide.", file=sys.stderr)
        return 1
    background = logo.getpixel((0, 0))
    if background[3] < 255:
        background = GREEN  # a transparent corner means the logo brings no tile of its own

    web = ROOT / "web" / "public"
    save(logo, web / "icon-192.png", 192)
    save(logo, web / "icon-512.png", 512)
    save(padded(logo, 512, 0.7, background), web / "icon-maskable-512.png")
    save(padded(logo, 180, 1.0, background), web / "apple-touch-icon.png")

    save(logo, ROOT / "packaging" / "icon.png", 512)
    ico_sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
    logo.save(ROOT / "packaging" / "icon.ico", sizes=ico_sizes)
    print("wrote packaging/icon.ico")
    logo.resize((1024, 1024), Image.Resampling.LANCZOS).save(ROOT / "packaging" / "icon.icns")
    print("wrote packaging/icon.icns")

    android = ROOT / "android-app" / "resources"
    save(logo, android / "icon-only.png", 1024)
    save(padded(logo, 1024, 0.62, background), android / "icon-foreground.png")
    save(Image.new("RGBA", (1024, 1024), background), android / "icon-background.png")
    splash = Image.new("RGBA", (2732, 2732), background)
    splash.alpha_composite(logo.resize((720, 720), Image.Resampling.LANCZOS), (1006, 1006))
    save(splash, android / "splash.png")

    for name in ("logo.svg",):
        if (BRAND / name).is_file():
            (web / "brand").mkdir(parents=True, exist_ok=True)
            shutil.copyfile(BRAND / name, web / "brand" / name)
            shutil.copyfile(BRAND / name, web / "icon.svg")
            shutil.copyfile(BRAND / name, ROOT / "android-app" / "www" / name)
            print("wrote the logo.svg copies under web/public and android-app/www")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
