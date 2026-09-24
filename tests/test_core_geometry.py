import pytest
from hypothesis import given
from hypothesis import strategies as st

from katib.core.geometry import (
    box_to_pixels,
    box_to_yolo,
    pixels_to_box,
    polygon_area,
    polygon_to_box,
    yolo_to_box,
)
from katib.core.types import Box, GeometryError, Polygon, geometry_bounds, validate_geometry

size = st.floats(min_value=0.001, max_value=1.0, allow_nan=False)


@st.composite
def boxes(draw: st.DrawFn) -> Box:
    w = draw(size)
    h = draw(size)
    x = draw(st.floats(min_value=0.0, max_value=1.0 - w))
    y = draw(st.floats(min_value=0.0, max_value=1.0 - h))
    return Box(x=x, y=y, w=w, h=h)


@given(boxes())
def test_yolo_round_trip(box: Box) -> None:
    back = yolo_to_box(*box_to_yolo(box))
    assert back.x == pytest.approx(box.x, abs=1e-9)
    assert back.w == pytest.approx(box.w, abs=1e-9)
    assert back.y == pytest.approx(box.y, abs=1e-9)
    assert back.h == pytest.approx(box.h, abs=1e-9)


@given(boxes(), st.integers(1, 10_000), st.integers(1, 10_000))
def test_pixel_round_trip(box: Box, width: int, height: int) -> None:
    back = pixels_to_box(*box_to_pixels(box, width, height), width, height)
    assert back.x == pytest.approx(box.x, abs=1e-9)
    assert back.h == pytest.approx(box.h, abs=1e-9)


def test_yolo_box_past_edge_is_clipped() -> None:
    box = yolo_to_box(0.98, 0.5, 0.1, 0.2)
    assert box.x + box.w == pytest.approx(1.0)


def test_box_past_edge_is_rejected() -> None:
    with pytest.raises(GeometryError, match="edge"):
        validate_geometry("box", {"x": 0.9, "y": 0.1, "w": 0.2, "h": 0.1})


@pytest.mark.parametrize(
    "geometry",
    [
        {"x": 0.1, "y": 0.1, "w": 0, "h": 0.1},
        {"x": -0.1, "y": 0.1, "w": 0.1, "h": 0.1},
        {"x": 0.1, "y": 0.1, "w": 0.1},
        {"x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1, "extra": 1},
    ],
)
def test_bad_boxes_are_rejected(geometry: dict[str, float]) -> None:
    with pytest.raises(GeometryError):
        validate_geometry("box", geometry)


def test_polygon_needs_three_points() -> None:
    with pytest.raises(GeometryError):
        validate_geometry("polygon", {"points": [[0.1, 0.1], [0.2, 0.2]]})


def test_unknown_type_is_rejected() -> None:
    with pytest.raises(GeometryError, match="Unknown"):
        validate_geometry("hexagon", {})


def test_polygon_area_and_bounds() -> None:
    poly = Polygon(points=[(0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5)])
    assert polygon_area(poly) == pytest.approx(0.25)
    box = polygon_to_box(poly)
    assert (box.x, box.y, box.w, box.h) == (0.0, 0.0, 0.5, 0.5)
    bounds = geometry_bounds("polygon", {"points": [[0, 0], [0.5, 0], [0.5, 0.5]]})
    assert bounds == (0, 0, 0.5, 0.5)
