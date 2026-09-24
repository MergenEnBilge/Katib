"""Annotation geometry types.

Geometry is normalized: 0 to 1 with the origin at the top-left of the image, so it does not
depend on resolution. New annotation types register here with a model, a validator and a
bounds function (ARCHITECTURE.md section 7).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

EPS = 1e-9

Unit = Annotated[float, Field(ge=0.0, le=1.0)]


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


Bounds = tuple[float, float, float, float]  # x, y, w, h


def box_bounds(g: Box) -> Bounds:
    return (g.x, g.y, g.w, g.h)


def polygon_bounds(g: Polygon) -> Bounds:
    xs = [p[0] for p in g.points]
    ys = [p[1] for p in g.points]
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


@dataclass(frozen=True)
class AnnotationType:
    name: str
    model: type[BaseModel]
    bounds: Callable[[Any], Bounds]


_REGISTRY: dict[str, AnnotationType] = {
    "box": AnnotationType("box", Box, box_bounds),
    "polygon": AnnotationType("polygon", Polygon, polygon_bounds),
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


def geometry_bounds(type_name: str, geometry: dict[str, Any]) -> Bounds:
    spec = _REGISTRY[type_name]
    return spec.bounds(validate_geometry(type_name, geometry))
