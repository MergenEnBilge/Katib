"""Attribute schemas on classes: a list of {name, type, options?} definitions."""

from typing import Any

ATTR_TYPES = ("boolean", "enum", "text", "number")
MAX_ATTRS = 20
MAX_TEXT = 500


class AttributeError_(ValueError):
    """A schema or a value is not valid. The message is shown to the person."""


def normalize_schema(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check a schema and return it in canonical form."""
    if len(raw) > MAX_ATTRS:
        raise AttributeError_(f"A class can have up to {MAX_ATTRS} attributes.")
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in raw:
        name = str(item.get("name", "")).strip()
        kind = item.get("type")
        if not name:
            raise AttributeError_("Every attribute needs a name.")
        if name.lower() in seen:
            raise AttributeError_(f"Two attributes are called “{name}”.")
        seen.add(name.lower())
        if kind not in ATTR_TYPES:
            raise AttributeError_(f"“{name}” has an unknown type.")
        entry: dict[str, Any] = {"name": name, "type": kind}
        if kind == "enum":
            given: list[Any] = list(item.get("options") or [])
            options = [str(o).strip() for o in given if str(o).strip()]
            if len(set(options)) != len(options) or len(options) < 2:
                raise AttributeError_(f"“{name}” needs at least two different options.")
            entry["options"] = options
        out.append(entry)
    return out


def check_attrs(schema: list[dict[str, Any]], attrs: dict[str, Any]) -> None:
    """Validate values for attributes the schema defines. Other keys are kept and ignored."""
    defs = {a["name"]: a for a in schema}
    for name, value in attrs.items():
        spec = defs.get(name)
        if spec is None or value is None:
            continue
        kind = spec["type"]
        if kind == "boolean" and not isinstance(value, bool):
            raise AttributeError_(f"“{name}” must be on or off.")
        if kind == "number" and (isinstance(value, bool) or not isinstance(value, int | float)):
            raise AttributeError_(f"“{name}” must be a number.")
        if kind == "text" and (not isinstance(value, str) or len(value) > MAX_TEXT):
            raise AttributeError_(f"“{name}” must be text of up to {MAX_TEXT} characters.")
        if kind == "enum" and value not in spec["options"]:
            raise AttributeError_(f"“{name}” must be one of {', '.join(spec['options'])}.")
