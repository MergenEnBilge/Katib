"""Default class colors (DESIGN.md section 2)."""

import colorsys

DEFAULT_PALETTE = [
    "#4C8DF6",
    "#8B6CF0",
    "#E86FB0",
    "#F2994A",
    "#2EC4D6",
    "#F2C94C",
    "#D16BF0",
    "#5B7CFA",
    "#FF8A65",
    "#7FB3FF",
]

GOLDEN_ANGLE = 137.508
MIN_DISTANCE = 40.0


def _rgb(color: str) -> tuple[int, int, int]:
    return (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))


def _distance(a: str, b: str) -> float:
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return float(((ra - rb) ** 2 + (ga - gb) ** 2 + (ba - bb) ** 2) ** 0.5)


def next_color(used: list[str]) -> str:
    """Pick the next unused default, then rotate hue by the golden angle.

    Generated colors skip any that sit too close to a color already in use. If the palette is
    crowded, the distance requirement relaxes so a new class always gets some color.
    """
    lowered = {c.lower() for c in used}
    for color in DEFAULT_PALETTE:
        if color.lower() not in lowered:
            return color
    for min_distance in (MIN_DISTANCE, 25.0, 10.0, 1.0):
        hue = 0.0
        for _ in range(400):
            hue = (hue + GOLDEN_ANGLE) % 360
            r, g, b = colorsys.hls_to_rgb(hue / 360, 0.62, 0.7)
            candidate = f"#{round(r * 255):02X}{round(g * 255):02X}{round(b * 255):02X}"
            if all(_distance(candidate, u) >= min_distance for u in used):
                return candidate
    return DEFAULT_PALETTE[len(used) % len(DEFAULT_PALETTE)]
