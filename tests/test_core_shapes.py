import math

import pytest

from katib.core import rle
from katib.core.types import GeometryError, Obb, geometry_bounds, obb_corners, validate_geometry


def test_a_box_turned_a_quarter_swaps_its_width_and_height_on_a_square_image() -> None:
    corners = obb_corners(Obb(cx=0.5, cy=0.5, w=0.4, h=0.2, angle=math.pi / 2), (100, 100))
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    assert max(xs) - min(xs) == pytest.approx(0.2)
    assert max(ys) - min(ys) == pytest.approx(0.4)


def test_rotation_happens_in_pixels_so_wide_images_stay_undistorted() -> None:
    # 200 by 100 pixels: a box 0.5 wide is 100 px wide, and 0.5 tall is 50 px tall.
    bounds = geometry_bounds(
        "obb", {"cx": 0.5, "cy": 0.5, "w": 0.5, "h": 0.5, "angle": math.pi / 2}, (200, 100)
    )
    assert bounds[2] == pytest.approx(0.25)  # 50 px of 200
    assert bounds[3] == pytest.approx(1.0)  # 100 px of 100


def test_keypoints_bounds_ignore_points_that_are_not_labeled() -> None:
    geometry = {
        "points": [
            {"x": 0.2, "y": 0.3, "v": 2},
            {"x": 0.6, "y": 0.7, "v": 1},
            {"x": 0.0, "y": 0.0, "v": 0},
        ]
    }
    assert geometry_bounds("keypoints", geometry) == pytest.approx((0.2, 0.3, 0.4, 0.4))


def test_keypoint_visibility_must_be_0_1_or_2() -> None:
    with pytest.raises(GeometryError):
        validate_geometry("keypoints", {"points": [{"x": 0.1, "y": 0.1, "v": 3}]})


def test_a_tag_has_no_geometry_and_covers_the_image() -> None:
    validate_geometry("tag", {})
    assert geometry_bounds("tag", {}) == (0.0, 0.0, 1.0, 1.0)
    with pytest.raises(GeometryError):
        validate_geometry("tag", {"x": 1})


def test_mask_runs_must_fill_the_grid() -> None:
    validate_geometry("mask", {"rle": "0,4,12", "size": [4, 4]})
    with pytest.raises(GeometryError, match="add up"):
        validate_geometry("mask", {"rle": "0,4,11", "size": [4, 4]})


def test_run_lengths_round_trip() -> None:
    cells = [False, False, True, True, True, False, True, False, False, False]
    text = rle.encode(cells)
    assert text == "2,3,1,1,3"
    assert rle.decode(text, 5, 2) == cells


def test_a_mask_starting_on_encodes_an_empty_first_run() -> None:
    assert rle.encode([True, True, False]) == "0,2,1"


def test_mask_bounds_cover_the_marked_cells() -> None:
    # A 4 by 4 grid with cells (1,1) and (2,2) on: runs 5 off, 1 on, 4 off, 1 on, 5 off.
    assert rle.bounds("5,1,4,1,5", 4, 4) == (0.25, 0.25, 0.5, 0.5)
    assert rle.bounds("16", 4, 4) is None


def test_a_run_over_several_rows_spans_the_full_width() -> None:
    assert rle.bounds("2,6,8", 4, 4) == (0.0, 0.0, 1.0, 0.5)
