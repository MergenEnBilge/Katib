"""Run-length encoding for brush masks.

A mask is a grid of on/off cells, read row by row. It is stored as the lengths of alternating
runs, starting with a run of off cells (which may be empty). "0,5,3,2" on a 10 cell grid means
five off cells, three on, two off. The grid is stretched over the whole image, so it does not
depend on the photo's resolution.
"""

MAX_CELLS = 2048 * 2048


class RleError(ValueError):
    """The mask text is not a valid run-length encoding for its grid."""


def encode(cells: list[bool]) -> str:
    """Turn a flat list of on/off cells into run lengths."""
    runs: list[int] = []
    current = False
    count = 0
    for cell in cells:
        if cell == current:
            count += 1
        else:
            runs.append(count)
            current = cell
            count = 1
    runs.append(count)
    return ",".join(str(r) for r in runs)


def parse(text: str, width: int, height: int) -> list[int]:
    """Read run lengths and check that they fill exactly a `width` by `height` grid."""
    if width < 1 or height < 1 or width * height > MAX_CELLS:
        raise RleError("The mask grid has an unsupported size.")
    try:
        runs = [int(part) for part in text.split(",")]
    except ValueError:
        raise RleError("The mask has to be a list of whole numbers.") from None
    if any(r < 0 for r in runs):
        raise RleError("Mask runs cannot be negative.")
    if sum(runs) != width * height:
        raise RleError("The mask runs do not add up to the grid size.")
    return runs


def decode(text: str, width: int, height: int) -> list[bool]:
    cells: list[bool] = []
    on = False
    for run in parse(text, width, height):
        cells.extend([on] * run)
        on = not on
    return cells


def bounds(text: str, width: int, height: int) -> tuple[float, float, float, float] | None:
    """Where the on cells are, as x, y, w, h fractions of the grid. None when nothing is on."""
    left, right, top, bottom = width, -1, height, -1
    position = 0
    on = False
    for run in parse(text, width, height):
        if on and run > 0:
            first, last = position, position + run - 1
            top = min(top, first // width)
            bottom = max(bottom, last // width)
            if first // width == last // width:
                left = min(left, first % width)
                right = max(right, last % width)
            else:
                left, right = 0, width - 1
        position += run
        on = not on
    if right < 0:
        return None
    return (left / width, top / height, (right - left + 1) / width, (bottom - top + 1) / height)
