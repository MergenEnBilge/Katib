import random

import pytest
from hypothesis import given
from hypothesis import strategies as st

from katib.core.quality import (
    BoxItem,
    duplicate_shapes,
    hamming,
    imbalance_ratio,
    iou,
    is_tiny,
    near_duplicates,
)
from katib.core.split import SplitError, SplitItem, assign_splits


def box(
    id: str, x: float, y: float, w: float, h: float, image: str = "i", cls: str = "c"
) -> BoxItem:
    return BoxItem(id, image, cls, x, y, w, h)


def test_tiny_shapes() -> None:
    assert is_tiny(0.005, 0.5)
    assert is_tiny(0.01, 0.01)
    assert not is_tiny(0.1, 0.1)


def test_iou() -> None:
    a = box("a", 0, 0, 0.5, 0.5)
    assert iou(a, a) == pytest.approx(1.0)
    assert iou(a, box("b", 0.5, 0.5, 0.5, 0.5)) == 0.0
    assert iou(a, box("c", 0.25, 0, 0.5, 0.5)) == pytest.approx(1 / 3)


def test_duplicates_need_same_image_class_and_near_identical_boxes() -> None:
    items = [
        box("a", 0.1, 0.1, 0.3, 0.3),
        box("b", 0.101, 0.1, 0.3, 0.3),
        box("c", 0.1, 0.1, 0.3, 0.3, cls="other"),
        box("d", 0.1, 0.1, 0.3, 0.3, image="j"),
        box("e", 0.5, 0.5, 0.2, 0.2),
    ]
    assert duplicate_shapes(items) == [("a", "b")]


def test_imbalance() -> None:
    assert imbalance_ratio([100, 10, 0]) == 10
    assert imbalance_ratio([5]) is None
    assert imbalance_ratio([]) is None


def test_near_duplicates_group_by_hamming_distance() -> None:
    base = 0x0F0F_0F0F_0F0F_0F0F
    hashes = {
        "a": base,
        "b": base ^ 0b101,  # 2 bits away
        "c": base ^ (1 << 40),  # 1 bit away
        "far": base ^ ((1 << 32) - 1),
        "solo": 0xFFFF_0000_FFFF_0000,
    }
    assert near_duplicates(hashes) == [["a", "b", "c"]]


@given(st.lists(st.integers(0, 2**64 - 1), min_size=2, max_size=40, unique=True))
def test_near_duplicates_matches_brute_force(values: list[int]) -> None:
    hashes = {f"k{i}": v for i, v in enumerate(values)}
    # Force some close pairs so the interesting case is exercised.
    keys = list(hashes)
    hashes[keys[0] + "x"] = hashes[keys[0]] ^ 0b11
    expected_pairs = {
        (a, b) for a in hashes for b in hashes if a < b and hamming(hashes[a], hashes[b]) <= 4
    }
    grouped = {(a, b) for g in near_duplicates(hashes) for a in g for b in g if a < b}
    # Every close pair must share a group. Groups may also link pairs through a third image.
    assert expected_pairs <= grouped


def items(n: int, classes: list[str] | None = None) -> list[SplitItem]:
    return [
        SplitItem(f"img{i}", frozenset([classes[i % len(classes)]]) if classes else frozenset())
        for i in range(n)
    ]


def test_random_split_sizes_and_determinism() -> None:
    ratios = {"train": 0.8, "val": 0.1, "test": 0.1}
    a = assign_splits(items(100), ratios, seed=7)
    b = assign_splits(items(100), ratios, seed=7)
    c = assign_splits(items(100), ratios, seed=8)
    assert a == b and a != c
    counts = {s: list(a.values()).count(s) for s in ratios}
    assert counts == {"train": 80, "val": 10, "test": 10}


def test_every_item_lands_in_exactly_one_split() -> None:
    result = assign_splits(items(37), {"train": 0.7, "val": 0.3}, seed=1)
    assert len(result) == 37 and set(result.values()) == {"train", "val"}


def test_stratified_keeps_rare_class_in_both_splits() -> None:
    data = [SplitItem(f"a{i}", frozenset({"common"})) for i in range(90)]
    data += [SplitItem(f"r{i}", frozenset({"rare"})) for i in range(10)]
    result = assign_splits(data, {"train": 0.8, "val": 0.2}, seed=3, stratify=True)
    rare = [result[f"r{i}"] for i in range(10)]
    assert rare.count("val") == 2 and rare.count("train") == 8


def test_bad_ratios_and_duplicate_keys() -> None:
    with pytest.raises(SplitError):
        assign_splits(items(3), {"train": 0})
    with pytest.raises(SplitError):
        assign_splits([SplitItem("a"), SplitItem("a")], {"train": 1})


@given(st.integers(1, 200), st.integers(0, 1000))
def test_partition_never_drops_items(n: int, seed: int) -> None:
    rnd = random.Random(seed)
    ratios = {"train": rnd.uniform(0.1, 1), "val": rnd.uniform(0.1, 1), "test": rnd.uniform(0.1, 1)}
    assert len(assign_splits(items(n), ratios, seed=seed)) == n
