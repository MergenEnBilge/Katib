"""Turning a detection model's raw output into boxes on the original image.

The model sees a square copy of the picture: scaled to fit and padded with gray ("letterboxed").
Its output has to be undone: boxes moved back by the padding, scaled back up, and clipped to
the picture. This module holds that arithmetic on plain lists, so it can be tested without a
model or any numeric library.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

Layout = Literal["v8", "v5"]

MIN_SIDE = 0.004


@dataclass(frozen=True)
class Letterbox:
    """How an image was fitted into the model's square input."""

    scale: float
    pad_x: float
    pad_y: float
    width: int
    height: int

    @classmethod
    def fit(cls, width: int, height: int, size: int) -> "Letterbox":
        scale = min(size / width, size / height)
        return cls(
            scale=scale,
            pad_x=(size - width * scale) / 2,
            pad_y=(size - height * scale) / 2,
            width=width,
            height=height,
        )


@dataclass(frozen=True)
class RawBox:
    """A candidate in the model's input pixels: center, size, class and score."""

    cx: float
    cy: float
    w: float
    h: float
    class_index: int
    score: float


@dataclass(frozen=True)
class Detection:
    """A box on the original image, as fractions of its width and height."""

    class_index: int
    score: float
    x: float
    y: float
    w: float
    h: float


def decode(rows: Sequence[Sequence[float]], layout: Layout, threshold: float) -> list[RawBox]:
    """Read candidates from model output that has already been arranged one row per candidate.

    `v8` rows are `cx, cy, w, h, score per class...`. `v5` rows are `cx, cy, w, h, objectness,
    score per class...`, and a class score is the objectness times that class's value.
    """
    lead = 5 if layout == "v5" else 4
    found: list[RawBox] = []
    for row in rows:
        scores = row[lead:]
        if not scores:
            continue
        best = max(range(len(scores)), key=scores.__getitem__)
        score = scores[best] * (row[4] if layout == "v5" else 1.0)
        if score >= threshold:
            found.append(RawBox(row[0], row[1], row[2], row[3], best, score))
    return found


def _iou(a: RawBox, b: RawBox) -> float:
    left = max(a.cx - a.w / 2, b.cx - b.w / 2)
    right = min(a.cx + a.w / 2, b.cx + b.w / 2)
    top = max(a.cy - a.h / 2, b.cy - b.h / 2)
    bottom = min(a.cy + a.h / 2, b.cy + b.h / 2)
    inter = max(0.0, right - left) * max(0.0, bottom - top)
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union > 0 else 0.0


def non_max_suppression(boxes: Sequence[RawBox], iou_threshold: float) -> list[RawBox]:
    """Keep the best box of each overlapping group.

    Boxes of different classes never suppress each other.
    """
    kept: list[RawBox] = []
    for box in sorted(boxes, key=lambda b: b.score, reverse=True):
        if all(k.class_index != box.class_index or _iou(k, box) < iou_threshold for k in kept):
            kept.append(box)
    return kept


def to_detections(boxes: Sequence[RawBox], fit: Letterbox) -> list[Detection]:
    """Move boxes from the model's input back onto the original image."""
    out: list[Detection] = []
    for b in boxes:
        left = (b.cx - b.w / 2 - fit.pad_x) / fit.scale / fit.width
        right = (b.cx + b.w / 2 - fit.pad_x) / fit.scale / fit.width
        top = (b.cy - b.h / 2 - fit.pad_y) / fit.scale / fit.height
        bottom = (b.cy + b.h / 2 - fit.pad_y) / fit.scale / fit.height
        left, right = max(0.0, left), min(1.0, right)
        top, bottom = max(0.0, top), min(1.0, bottom)
        if right - left < MIN_SIDE or bottom - top < MIN_SIDE:
            continue
        out.append(Detection(b.class_index, b.score, left, top, right - left, bottom - top))
    return out


def detect_boxes(
    rows: Sequence[Sequence[float]],
    layout: Layout,
    fit: Letterbox,
    threshold: float,
    iou_threshold: float = 0.45,
) -> list[Detection]:
    """Everything above: decode, suppress duplicates, and map back onto the picture."""
    return to_detections(non_max_suppression(decode(rows, layout, threshold), iou_threshold), fit)
