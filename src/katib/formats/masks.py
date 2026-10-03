"""Turning other tools' masks into Katib's own: a grid of on and off cells stretched over the
image, stored as run lengths (see `katib.core.rle`).

Two sources come through here: COCO's run-length masks, which count down columns rather than
along rows, and mask pictures, where every pixel's value says which class covers it. A mask
bigger than Katib's grid is sampled down to fit, which is far finer than any brush stroke.
"""

import math

from katib.core import rle


def grid_for(width: int, height: int) -> tuple[int, int, int]:
    """The grid a `width` x `height` mask is stored on, and the step between sampled pixels."""
    step = max(1, math.ceil(math.sqrt(width * height / rle.MAX_CELLS)))
    return math.ceil(width / step), math.ceil(height / step), step


def encode_rows(rows: list[bytes]) -> str:
    """Run lengths for a grid given as rows of 0 and non-zero bytes."""
    runs: list[int] = []
    current = False
    count = 0
    for row in rows:
        for value in row:
            on = value != 0
            if on == current:
                count += 1
            else:
                runs.append(count)
                current = on
                count = 1
    runs.append(count)
    return ",".join(str(r) for r in runs)


def from_rows(rows: list[bytes], width: int, height: int) -> dict[str, object] | None:
    """A mask geometry from full-size pixel rows (non-zero is on), or None when nothing is on."""
    if not any(any(row) for row in rows):
        return None
    grid_w, grid_h, step = grid_for(width, height)
    sampled = [rows[y][::step] for y in range(0, height, step)]
    return {"rle": encode_rows(sampled), "size": [grid_w, grid_h]}


def coco_counts(counts: object) -> list[int]:
    """COCO's run lengths, either as a plain list or in its compact text form."""
    if isinstance(counts, list):
        return [int(c) for c in counts]  # type: ignore[union-attr]
    if not isinstance(counts, str):
        raise ValueError("The mask has no counts.")
    out: list[int] = []
    p = 0
    while p < len(counts):
        x = 0
        k = 0
        more = True
        while more:
            c = ord(counts[p]) - 48
            x |= (c & 0x1F) << (5 * k)
            more = bool(c & 0x20)
            p += 1
            k += 1
            if not more and (c & 0x10):
                x |= -1 << (5 * k)
        if len(out) > 2:
            x += out[-2]
        out.append(x)
    return out


def from_coco(segmentation: dict[str, object]) -> dict[str, object] | None:
    """A Katib mask from a COCO run-length mask: `{"size": [h, w], "counts": ...}`."""
    size = segmentation.get("size")
    if not isinstance(size, list) or len(size) != 2:  # type: ignore[arg-type]
        raise ValueError("The mask has no size.")
    height, width = int(size[0]), int(size[1])  # type: ignore[index]
    total = width * height
    # COCO runs go down each column in turn, starting with an off run.
    columns = bytearray(total)
    position = 0
    on = False
    for run in coco_counts(segmentation.get("counts")):
        if on and run:
            columns[position : position + run] = b"\x01" * run
        position += run
        on = not on
    if position != total:
        raise ValueError("The mask runs do not fill the picture.")
    rows = [bytes(columns[y::height]) for y in range(height)]
    return from_rows(rows, width, height)
