from katib.core import mask as mask_module


def grid(width: int, height: int, cells: list[tuple[int, int]]) -> list[int]:
    data = [0] * (width * height)
    for x, y in cells:
        data[y * width + x] = 1
    return data


def rectangle(width: int, height: int, left: int, top: int, right: int, bottom: int) -> list[int]:
    cells = [(x, y) for y in range(top, bottom) for x in range(left, right)]
    return grid(width, height, cells)


def test_a_square_becomes_a_handful_of_corners() -> None:
    """The ring is closed, so the point next to where the walk started survives simplifying."""
    found = mask_module.polygon(rectangle(20, 20, 4, 4, 14, 14), 20, 20)
    assert found is not None
    assert 4 <= len(found) <= 6
    xs = [x * 20 for x, _ in found]
    ys = [y * 20 for _, y in found]
    assert (min(xs), max(xs)) == (4.5, 13.5)
    assert (min(ys), max(ys)) == (4.5, 13.5)


def test_stray_cells_elsewhere_are_left_out() -> None:
    """A model asked about one object often marks a speck across the picture as well."""
    data = rectangle(20, 20, 2, 2, 12, 12)
    for cell in [(18, 18), (18, 17), (17, 18)]:
        data[cell[1] * 20 + cell[0]] = 1
    found = mask_module.polygon(data, 20, 20)
    assert found is not None
    assert all(x < 0.7 and y < 0.7 for x, y in found)


def test_nothing_to_trace_gives_nothing() -> None:
    assert mask_module.polygon([0] * 400, 20, 20) is None
    assert mask_module.polygon(grid(20, 20, [(5, 5), (5, 6)]), 20, 20) is None


def test_the_outline_stays_inside_the_picture() -> None:
    found = mask_module.polygon(rectangle(16, 16, 0, 0, 16, 16), 16, 16)
    assert found is not None
    assert all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in found)


def test_a_long_straight_edge_is_not_kept_point_by_point() -> None:
    line = [(x, 5) for x in range(2, 18)] + [(x, 6) for x in range(2, 18)]
    walked = mask_module.trace_outline(grid(20, 20, line), 20, 20)
    ring = mask_module.simplify(walked, 1.5)
    assert len(walked) > 20
    assert len(ring) <= 5
