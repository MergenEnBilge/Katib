"""Dataset quality checks on plain values: tiny and duplicate shapes, imbalance, look-alikes."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

TINY_SIDE = 0.01
TINY_AREA = 0.0002
DUPLICATE_IOU = 0.95
NEAR_DUPLICATE_BITS = 4
_SEGMENTS = NEAR_DUPLICATE_BITS + 1


@dataclass(frozen=True)
class BoxItem:
    id: str
    image_id: str
    class_id: str
    x: float
    y: float
    w: float
    h: float


def is_tiny(w: float, h: float) -> bool:
    """A shape this small is usually a stray click. Sides are fractions of the image."""
    return w < TINY_SIDE or h < TINY_SIDE or w * h < TINY_AREA


def iou(a: BoxItem, b: BoxItem) -> float:
    ix = max(0.0, min(a.x + a.w, b.x + b.w) - max(a.x, b.x))
    iy = max(0.0, min(a.y + a.h, b.y + b.h) - max(a.y, b.y))
    inter = ix * iy
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union > 0 else 0.0


def duplicate_shapes(items: Sequence[BoxItem]) -> list[tuple[str, str]]:
    """Pairs of shapes on the same image and class that overlap almost exactly."""
    by_key: dict[tuple[str, str], list[BoxItem]] = defaultdict(list)
    for item in items:
        by_key[(item.image_id, item.class_id)].append(item)
    pairs: list[tuple[str, str]] = []
    for group in by_key.values():
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                if iou(a, b) >= DUPLICATE_IOU:
                    pairs.append((a.id, b.id))
    return pairs


def imbalance_ratio(counts: Sequence[int]) -> float | None:
    """Largest class count over the smallest non-empty one, or None with fewer than two classes."""
    filled = [c for c in counts if c > 0]
    if len(filled) < 2:
        return None
    return max(filled) / min(filled)


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def near_duplicates(hashes: dict[str, int], max_bits: int = NEAR_DUPLICATE_BITS) -> list[list[str]]:
    """Group images whose 64-bit perceptual hashes differ in at most `max_bits` bits.

    Splitting the hash into max_bits + 1 segments guarantees that two hashes within the limit share
    at least one identical segment, so only images in the same bucket need comparing.
    """
    segments = max_bits + 1
    width = 64 // segments
    buckets: dict[tuple[int, int], list[str]] = defaultdict(list)
    for key, value in hashes.items():
        for s in range(segments):
            lo = s * width
            hi = 64 if s == segments - 1 else lo + width
            part = (value >> lo) & ((1 << (hi - lo)) - 1)
            buckets[(s, part)].append(key)

    parent: dict[str, str] = {}

    def find(k: str) -> str:
        while parent.setdefault(k, k) != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    seen: set[tuple[str, str]] = set()
    for members in buckets.values():
        if len(members) < 2 or len(members) > 2000:
            continue
        for i, a in enumerate(members):
            for b in members[i + 1 :]:
                pair = (a, b) if a < b else (b, a)
                if pair in seen:
                    continue
                seen.add(pair)
                if hamming(hashes[a], hashes[b]) <= max_bits:
                    parent[find(a)] = find(b)
    groups: dict[str, list[str]] = defaultdict(list)
    for key in parent:
        groups[find(key)].append(key)
    return sorted((sorted(g) for g in groups.values() if len(g) > 1), key=lambda g: g[0])
