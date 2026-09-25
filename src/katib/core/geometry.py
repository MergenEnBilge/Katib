"""Coordinate conversions between normalized geometry and formats that use pixels or centers."""

import math

from katib.core.types import Box, Obb, Polygon, obb_corners


def box_to_yolo(box: Box) -> tuple[float, float, float, float]:
    """Return (cx, cy, w, h), all normalized."""
    return (box.x + box.w / 2, box.y + box.h / 2, box.w, box.h)


def yolo_to_box(cx: float, cy: float, w: float, h: float) -> Box:
    """Build a box from YOLO values, clipped to the image so slightly-off files still import."""
    x0 = max(0.0, cx - w / 2)
    y0 = max(0.0, cy - h / 2)
    x1 = min(1.0, cx + w / 2)
    y1 = min(1.0, cy + h / 2)
    return Box(x=x0, y=y0, w=x1 - x0, h=y1 - y0)


def box_to_pixels(box: Box, width: int, height: int) -> tuple[float, float, float, float]:
    """Return (x, y, w, h) in pixels."""
    return (box.x * width, box.y * height, box.w * width, box.h * height)


def pixels_to_box(x: float, y: float, w: float, h: float, width: int, height: int) -> Box:
    x0 = max(0.0, x / width)
    y0 = max(0.0, y / height)
    x1 = min(1.0, (x + w) / width)
    y1 = min(1.0, (y + h) / height)
    return Box(x=x0, y=y0, w=x1 - x0, h=y1 - y0)


def polygon_to_pixels(poly: Polygon, width: int, height: int) -> list[tuple[float, float]]:
    return [(px * width, py * height) for px, py in poly.points]


def pixels_to_polygon(points: list[tuple[float, float]], width: int, height: int) -> Polygon:
    return Polygon(
        points=[
            (min(1.0, max(0.0, px / width)), min(1.0, max(0.0, py / height))) for px, py in points
        ]
    )


def polygon_area(poly: Polygon) -> float:
    """Shoelace area in normalized units squared."""
    pts = poly.points
    total = 0.0
    for i, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2


def polygon_to_box(poly: Polygon) -> Box:
    xs = [p[0] for p in poly.points]
    ys = [p[1] for p in poly.points]
    return Box(x=min(xs), y=min(ys), w=max(xs) - min(xs), h=max(ys) - min(ys))


def obb_from_corners(points: list[tuple[float, float]], width: int, height: int) -> Obb:
    """Build a rotated box from four normalized corners given in drawing order.

    The sides are measured in pixels, so an image that is not square does not skew the angle.
    """
    if len(points) != 4:
        raise ValueError("A rotated box has four corners.")
    px = [(x * width, y * height) for x, y in points]
    (x0, y0), (x1, y1), (x2, y2), _ = px
    side_w = math.hypot(x1 - x0, y1 - y0)
    side_h = math.hypot(x2 - x1, y2 - y1)
    cx = sum(p[0] for p in px) / 4 / width
    cy = sum(p[1] for p in px) / 4 / height
    return Obb(
        cx=min(1.0, max(0.0, cx)),
        cy=min(1.0, max(0.0, cy)),
        w=min(1.0, side_w / width),
        h=min(1.0, side_h / height),
        angle=math.atan2(y1 - y0, x1 - x0),
    )


def obb_to_polygon(obb: Obb, width: int, height: int) -> Polygon:
    """The four corners as a polygon, clipped to the image."""
    corners = obb_corners(obb, (width, height))
    return Polygon(points=[(min(1.0, max(0.0, x)), min(1.0, max(0.0, y))) for x, y in corners])


def box_to_polygon(box: Box) -> Polygon:
    return Polygon(
        points=[
            (box.x, box.y),
            (min(1.0, box.x + box.w), box.y),
            (min(1.0, box.x + box.w), min(1.0, box.y + box.h)),
            (box.x, min(1.0, box.y + box.h)),
        ]
    )
