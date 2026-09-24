"""Train, validation and test splits. Deterministic for a given seed."""

import hashlib
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

SPLITS = ("train", "val", "test")


@dataclass(frozen=True)
class SplitItem:
    key: str
    #: Class ids present on the image. Used to keep rare classes in every split.
    classes: frozenset[str] = frozenset()


class SplitError(ValueError):
    """The ratios are not usable."""


def _order(key: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()


def _partition(keys: list[str], ratios: dict[str, float]) -> dict[str, str]:
    total = len(keys)
    names = [n for n in SPLITS if ratios.get(n, 0) > 0]
    weight = sum(ratios[n] for n in names)
    result: dict[str, str] = {}
    start = 0
    for i, name in enumerate(names):
        size = total - start if i == len(names) - 1 else round(total * ratios[name] / weight)
        for key in keys[start : start + size]:
            result[key] = name
        start += size
    return result


def assign_splits(
    items: Sequence[SplitItem],
    ratios: dict[str, float],
    seed: int = 0,
    stratify: bool = False,
    class_counts: dict[str, int] | None = None,
) -> dict[str, str]:
    """Return a split name for every item key.

    Random: shuffle by seed, then cut by ratio. Stratified: group images by their rarest class
    and cut each group by ratio, so every split sees every class where the data allows.
    """
    if any(v < 0 for v in ratios.values()) or sum(ratios.values()) <= 0:
        raise SplitError("Split ratios must be positive numbers.")
    keys = [i.key for i in items]
    if len(set(keys)) != len(keys):
        raise SplitError("Item keys must be unique.")
    if not stratify:
        return _partition(sorted(keys, key=lambda k: _order(k, seed)), ratios)

    counts = class_counts or defaultdict(int)
    if not class_counts:
        for item in items:
            for c in item.classes:
                counts[c] += 1
    groups: dict[str, list[str]] = defaultdict(list)
    for item in items:
        rarest = min(item.classes, key=lambda c: (counts[c], c)) if item.classes else ""
        groups[rarest].append(item.key)
    result: dict[str, str] = {}
    for group in groups.values():
        result.update(_partition(sorted(group, key=lambda k: _order(k, seed)), ratios))
    return result
