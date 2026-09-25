"""Annotation geometry types.

Geometry is normalized: 0 to 1 with the origin at the top-left of the image, so it does not
depend on resolution. New annotation types register here with a model, a validator and a
bounds function (ARCHITECTURE.md section 7).
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from katib.core import rle

EPS = 1e-9

Unit = Annotated[float, Field(ge=0.0, le=1.0)]

Bounds = tuple[float, float, float, float]  # x, y, w, h
Size = tuple[int, int]  # image width and height in pixels


class GeometryError(ValueError):
    """Geometry is malformed for its type."""


class Box(BaseModel):
    """Top-left corner plus size."""

    model_config = ConfigDict(extra="forbid")

    x: Unit
    y: Unit
    w: float = Field(gt=0.0, le=1.0)
    h: float = Field(gt=0.0, le=1.0)

    @model_validator(mode="after")
    def _inside_image(self) -> "Box":
        if self.x + self.w > 1.0 + EPS or self.y + self.h > 1.0 + EPS:
            raise ValueError("box extends past the image edge")
        return self


class Polygon(BaseModel):
    """A single ring with at least three points."""

    model_config = ConfigDict(extra="forbid")

    points: list[tuple[Unit, Unit]] = Field(min_length=3)


class Obb(BaseModel):
    """A rotated box: center, size and angle in radians.

    The angle turns the box in pixel space, so what looks square on screen stays square whatever
    the image's shape. Working out the corners therefore needs the image size (`obb_corners`).
    """

    model_config = ConfigDict(extra="forbid")

    cx: Unit
    cy: Unit
    w: float = Field(gt=0.0, le=1.0)
    h: float = Field(gt=0.0, le=1.0)
    angle: float = Field(ge=-2 * math.pi, le=2 * math.pi)


class Keypoint(BaseModel):
    """One landmark. `v` is 0 when not labeled, 1 when hidden and 2 when visible."""

    model_config = ConfigDict(extra="forbid")

    x: Unit
    y: Unit
    v: Literal[0, 1, 2]


class Keypoints(BaseModel):
    """Landmarks in the order the class's skeleton lists them."""

    model_config = ConfigDict(extra="forbid")

    points: list[Keypoint] = Field(min_length=1, max_length=128)


class Mask(BaseModel):
    """A brush mask on a coarse grid stretched over the image. See `katib.core.rle`."""

    model_config = ConfigDict(extra="forbid")

    rle: str = Field(max_length=4_000_000)
    size: tuple[int, int]

    @model_validator(mode="after")
    def _runs_fit_grid(self) -> "Mask":
        try:
            rle.parse(self.rle, self.size[0], self.size[1])
        except rle.RleError as err:
            raise ValueError(str(err)) from None
        return self


class Tag(BaseModel):
    """A label for the whole image. It has no geometry."""

    model_config = ConfigDict(extra="forbid")


def box_bounds(g: Box, size: Size | None = None) -> Bounds:
    return (g.x, g.y, g.w, g.h)


def polygon_bounds(g: Polygon, size: Size | None = None) -> Bounds:
    xs = [p[0] for p in g.points]
    ys = [p[1] for p in g.points]
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def obb_corners(g: Obb, size: Size | None = None) -> list[tuple[float, float]]:
    """The four corners as normalized points. Without `size` the image is taken to be square."""
    width, height = size or (1, 1)
    cx, cy = g.cx * width, g.cy * height
    half_w, half_h = g.w * width / 2, g.h * height / 2
    cos, sin = math.cos(g.angle), math.sin(g.angle)
    corners: list[tuple[float, float]] = []
    for dx, dy in ((-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)):
        corners.append(((cx + dx * cos - dy * sin) / width, (cy + dx * sin + dy * cos) / height))
    return corners


def obb_bounds(g: Obb, size: Size | None = None) -> Bounds:
    corners = obb_corners(g, size)
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def keypoints_bounds(g: Keypoints, size: Size | None = None) -> Bounds:
    shown = [p for p in g.points if p.v > 0]
    if not shown:
        return (0.0, 0.0, 0.0, 0.0)
    xs = [p.x for p in shown]
    ys = [p.y for p in shown]
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def mask_bounds(g: Mask, size: Size | None = None) -> Bounds:
    return rle.bounds(g.rle, g.size[0], g.size[1]) or (0.0, 0.0, 0.0, 0.0)


def tag_bounds(g: Tag, size: Size | None = None) -> Bounds:
    return (0.0, 0.0, 1.0, 1.0)


@dataclass(frozen=True)
class AnnotationType:
    name: str
    model: type[BaseModel]
    bounds: Callable[[Any, Size | None], Bounds]


_REGISTRY: dict[str, AnnotationType] = {
    "box": AnnotationType("box", Box, box_bounds),
    "polygon": AnnotationType("polygon", Polygon, polygon_bounds),
    "obb": AnnotationType("obb", Obb, obb_bounds),
    "keypoints": AnnotationType("keypoints", Keypoints, keypoints_bounds),
    "mask": AnnotationType("mask", Mask, mask_bounds),
    "tag": AnnotationType("tag", Tag, tag_bounds),
}


def known_types() -> list[str]:
    return sorted(_REGISTRY)


def validate_geometry(type_name: str, geometry: dict[str, Any]) -> BaseModel:
    """Parse geometry for a type. Raises GeometryError with a readable message."""
    spec = _REGISTRY.get(type_name)
    if spec is None:
        raise GeometryError(f"Unknown annotation type {type_name!r}.")
    try:
        return spec.model.model_validate(geometry)
    except ValidationError as err:
        first = err.errors()[0]
        where = ".".join(str(p) for p in first["loc"]) or "root"
        raise GeometryError(f"Invalid {type_name} geometry at {where}: {first['msg']}") from err


def geometry_bounds(type_name: str, geometry: dict[str, Any], size: Size | None = None) -> Bounds:
    """The rectangle around a shape, as fractions of the image. `size` is the image in pixels."""
    spec = _REGISTRY[type_name]
    return spec.bounds(validate_geometry(type_name, geometry), size)
