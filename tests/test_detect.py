import pytest

from katib.core.detect import (
    Letterbox,
    RawBox,
    decode,
    detect_boxes,
    non_max_suppression,
    to_detections,
)


def test_a_wide_picture_is_padded_top_and_bottom() -> None:
    fit = Letterbox.fit(800, 400, 640)
    assert fit.scale == pytest.approx(0.8)
    assert (fit.pad_x, fit.pad_y) == pytest.approx((0.0, 160.0))


def test_v8_rows_use_the_best_class_score() -> None:
    rows = [[100, 100, 20, 20, 0.1, 0.9], [200, 200, 20, 20, 0.2, 0.3]]
    found = decode(rows, "v8", threshold=0.5)
    assert [(b.class_index, b.score) for b in found] == [(1, 0.9)]


def test_v5_scores_are_scaled_by_objectness() -> None:
    rows = [[100, 100, 20, 20, 0.5, 0.9, 0.1], [100, 100, 20, 20, 0.9, 0.9, 0.1]]
    found = decode(rows, "v5", threshold=0.6)
    assert len(found) == 1
    assert found[0].score == pytest.approx(0.81)


def test_overlapping_boxes_of_one_class_keep_only_the_best() -> None:
    a = RawBox(100, 100, 50, 50, 0, 0.9)
    b = RawBox(102, 101, 50, 50, 0, 0.6)
    c = RawBox(102, 101, 50, 50, 1, 0.6)
    kept = non_max_suppression([b, a, c], 0.45)
    assert kept == [a, c]


def test_boxes_map_back_onto_the_original_picture() -> None:
    fit = Letterbox.fit(800, 400, 640)
    [box] = to_detections([RawBox(320, 320, 160, 80, 0, 0.9)], fit)
    assert (box.x, box.y, box.w, box.h) == pytest.approx((0.375, 0.375, 0.25, 0.25))


def test_boxes_are_clipped_to_the_picture_and_dust_is_dropped() -> None:
    fit = Letterbox.fit(800, 400, 640)
    edge = RawBox(20, 320, 100, 80, 0, 0.9)
    dust = RawBox(320, 320, 1, 1, 0, 0.9)
    found = to_detections([edge, dust], fit)
    assert len(found) == 1
    assert found[0].x == 0.0
    assert found[0].x + found[0].w <= 1.0


def test_the_whole_pipeline() -> None:
    fit = Letterbox.fit(800, 400, 640)
    rows = [
        [320, 320, 160, 80, 0.95, 0.05],
        [322, 321, 160, 80, 0.7, 0.05],
        [50, 50, 10, 10, 0.1, 0.1],
    ]
    found = detect_boxes(rows, "v8", fit, threshold=0.5)
    assert [d.class_index for d in found] == [0]
