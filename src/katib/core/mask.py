"""Turning a mask into an outline somebody can drag corners of.

A segmentation model answers with a grid of on and off cells. An annotation is a polygon, so the
grid has to become one: keep the biggest connected piece, walk its edge, and drop the points that
sit on a straight run. It is the same arithmetic the magic wand does in the browser, on plain
lists, so it can be tested without a model or any numeric library.
"""

from collections.abc import Sequence

Point = tuple[int, int]

#: Clockwise from east. Walking the edge means always turning as far right as the shape allows.
NEIGHBORS: tuple[Point, ...] = (
    (1, 0),
    (1, 1),
    (0, 1),
    (-1, 1),
    (-1, 0),
    (-1, -1),
    (0, -1),
    (1, -1),
)

#: How far a point may sit from the line between its neighbours before it earns its place.
SIMPLIFY_PIXELS = 1.5

#: Fewer cells than this and it was a stray speck rather than an object.
MIN_CELLS = 16


def largest_region(mask: Sequence[int], width: int, height: int) -> bytearray:
    """Only the biggest connected piece of `mask`.

    A model asked about one object often marks a few loose cells elsewhere. Outlining those as
    well would produce a polygon that wanders across the picture.
    """
    seen = bytearray(width * height)
    best = bytearray(width * height)
    best_size = 0
    for start in range(width * height):
        if not mask[start] or seen[start]:
            continue
        piece: list[int] = []
        stack = [start]
        seen[start] = 1
        while stack:
            cell = stack.pop()
            piece.append(cell)
            x, y = cell % width, cell // width
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    neighbor = ny * width + nx
                    if mask[neighbor] and not seen[neighbor]:
                        seen[neighbor] = 1
                        stack.append(neighbor)
        if len(piece) > best_size:
            best_size = len(piece)
            best = bytearray(width * height)
            for cell in piece:
                best[cell] = 1
    return best


def trace_outline(region: Sequence[int], width: int, height: int) -> list[Point]:
    """The outer boundary of the piece holding the first marked cell, walked clockwise."""

    def on(x: int, y: int) -> bool:
        return 0 <= x < width and 0 <= y < height and bool(region[y * width + x])

    start = next((i for i in range(width * height) if region[i]), -1)
    if start < 0:
        return []
    start_x, start_y = start % width, start // width

    outline: list[Point] = [(start_x, start_y)]
    x, y = start_x, start_y
    # The cell above the first marked one is empty, so the search begins by looking west of it.
    came_from = 4
    for _ in range(width * height * 4):
        moved = False
        for step in range(1, 9):
            direction = (came_from + step) % 8
            dx, dy = NEIGHBORS[direction]
            if on(x + dx, y + dy):
                x, y = x + dx, y + dy
                came_from = (direction + 4) % 8
                moved = True
                break
        if not moved or (x, y) == (start_x, start_y):
            break
        outline.append((x, y))
    return outline


def simplify(points: list[Point], epsilon: float) -> list[Point]:
    """Douglas-Peucker: drop points within `epsilon` of the line between their neighbours."""
    if len(points) < 4:
        return points
    keep = bytearray(len(points))
    keep[0] = keep[-1] = 1
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        ax, ay = points[first]
        bx, by = points[last]
        length = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5 or 1.0
        far = -1
        farthest = epsilon
        for i in range(first + 1, last):
            px, py = points[i]
            away = abs((by - ay) * px - (bx - ax) * py + bx * ay - by * ax) / length
            if away > farthest:
                far = i
                farthest = away
        if far >= 0:
            keep[far] = 1
            stack.append((first, far))
            stack.append((far, last))
    return [p for i, p in enumerate(points) if keep[i]]


def polygon(
    mask: Sequence[int], width: int, height: int, epsilon: float = SIMPLIFY_PIXELS
) -> list[tuple[float, float]] | None:
    """An outline as fractions of the picture, or None when there is nothing worth tracing."""
    if sum(1 for cell in mask if cell) < MIN_CELLS:
        return None
    region = largest_region(mask, width, height)
    ring = simplify(trace_outline(region, width, height), epsilon)
    if len(ring) < 3:
        return None
    # The outline runs through cell centres. Shift it half a cell to sit on the edges the cells
    # really cover.
    return [
        (min(1.0, max(0.0, (x + 0.5) / width)), min(1.0, max(0.0, (y + 0.5) / height)))
        for x, y in ring
    ]
