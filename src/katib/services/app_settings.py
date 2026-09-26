"""The settings people can change from inside the app.

Each setting is described once here: its label, its help text, its limits and whether a change
takes effect straight away or after a restart. The API shows them and checks what people send
against the same list, so the screen and the rules cannot drift apart.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import ValidationError

from katib.config import DEFAULT_DATABASE_URL, Settings
from katib.services.errors import InvalidInput

Kind = str  # "bool", "int", "text", "choice", "paths"


@dataclass(frozen=True)
class Option:
    value: str
    label: str


@dataclass(frozen=True)
class Field:
    key: str  # "section.name", the same as the environment variable without KATIB_ and with dots
    group: str
    label: str
    help: str
    kind: Kind
    live: bool = False  # true when a change applies without a restart
    minimum: int | None = None
    maximum: int | None = None
    options: tuple[Option, ...] = ()
    allow_other: bool = False  # a choice that also accepts typing something else
    secret: bool = False

    @property
    def section(self) -> str:
        return self.key.split(".")[0]

    @property
    def name(self) -> str:
        return self.key.split(".")[1]

    @property
    def env_name(self) -> str:
        return f"KATIB_{self.section.upper()}__{self.name.upper()}"


GROUPS: tuple[tuple[str, str, str], ...] = (
    ("sharing", "Sharing", "Who can open Katib and how they reach it."),
    ("storage", "Storage", "Where Katib keeps your projects and which folders it may read."),
    ("limits", "Limits", "Keep uploads and undo history in check."),
    ("model", "Model help", "Let your own model draw first-guess boxes."),
)

FIELDS: tuple[Field, ...] = (
    Field(
        "auth.mode",
        "sharing",
        "Who uses this Katib",
        "Choose accounts before you let other people in. With accounts on, everyone signs in "
        "and each project has its own members and roles.",
        "choice",
        options=(
            Option("none", "Just me, on this computer"),
            Option("local", "A team, with accounts"),
        ),
    ),
    Field(
        "server.host",
        "sharing",
        "Reachable from",
        "Only this computer is the safe choice for one person. Pick everyone on my network to "
        "let phones and colleagues in. That needs accounts turned on.",
        "choice",
        options=(
            Option("127.0.0.1", "This computer only"),
            Option("0.0.0.0", "Everyone on my network"),  # noqa: S104
        ),
        allow_other=True,
    ),
    Field(
        "server.port",
        "sharing",
        "Port",
        "The number at the end of the address, as in :8420. Change it if something else already "
        "uses it.",
        "int",
        minimum=1,
        maximum=65535,
    ),
    Field(
        "server.public_url",
        "sharing",
        "Public address",
        "The address people type, such as https://katib.example.com. Katib shows it in the "
        "share window. Leave it empty on a home network.",
        "text",
        live=True,
    ),
    Field(
        "server.behind_proxy",
        "sharing",
        "Behind a reverse proxy",
        "Turn this on only when a proxy you run, such as Caddy, is the only way to reach Katib. "
        "Katib then trusts it about who is visiting and whether they used HTTPS.",
        "bool",
        live=True,
    ),
    Field(
        "storage.data_dir",
        "storage",
        "Data folder",
        "Where Katib keeps its database, thumbnails, uploads and undo history. Changing this "
        "does not move what is already there. Copy the old folder across first.",
        "text",
    ),
    Field(
        "storage.allowed_import_roots",
        "storage",
        "Folders Katib may read",
        "One folder per line. Katib reads pictures from these folders in place and never "
        "changes them. Folders you connect to a project are added here for you.",
        "paths",
        live=True,
    ),
    Field(
        "database.url",
        "storage",
        "Database",
        "The built-in database needs nothing from you and suits a team of a few people. Pick "
        "another address only if you already run Postgres. Your projects do not move with it.",
        "choice",
        options=(Option(DEFAULT_DATABASE_URL, "Built in, stored in the data folder"),),
        allow_other=True,
        secret=True,
    ),
    Field(
        "limits.max_upload_mb",
        "limits",
        "Largest upload, in MB",
        "The biggest picture the browser may upload.",
        "int",
        live=True,
        minimum=1,
        maximum=10240,
    ),
    Field(
        "limits.max_image_pixels",
        "limits",
        "Largest picture, in pixels",
        "Pictures with more pixels than this are refused. It protects the server from files "
        "made to use up its memory.",
        "int",
        live=True,
        minimum=1_000_000,
        maximum=2_000_000_000,
    ),
    Field(
        "limits.operation_retention_days",
        "limits",
        "Keep undo history for",
        "Days that bulk changes stay undoable. After that their undo data is deleted.",
        "int",
        live=True,
        minimum=1,
        maximum=3650,
    ),
    Field(
        "ml.enabled",
        "model",
        "Pre-label with a model",
        "Allow drafting boxes with an ONNX detection model that you provide. It needs the "
        "model extra installed.",
        "bool",
        live=True,
    ),
    Field(
        "ml.models_dir",
        "model",
        "Models folder",
        "Where your .onnx files live. Leave empty for the models folder inside the data folder.",
        "text",
        live=True,
    ),
)

BY_KEY = {f.key: f for f in FIELDS}
_HOST = re.compile(r"^[A-Za-z0-9.:_\-\[\]]+$")


@dataclass
class FieldState:
    field: Field
    value: Any  # what to show: the saved value when there is one, else what is running
    running: Any  # what the server is using now
    source: str  # "default", "saved" or "environment"
    restart_pending: bool = False
    env_name: str | None = None


@dataclass
class Snapshot:
    """The settings as the server started, to tell which saved changes still wait for a restart."""

    values: dict[str, Any] = field(default_factory=dict[str, Any])


def read_value(settings: Settings, key: str) -> Any:
    section, name = key.split(".")
    value: Any = getattr(getattr(settings, section), name)
    return value


def snapshot(settings: Settings) -> Snapshot:
    values = {f.key: _plain(read_value(settings, f.key)) for f in FIELDS}
    values["storage.data_dir"] = str(settings.data_dir)
    return Snapshot(values)


def _plain(value: Any) -> Any:
    return list(value) if isinstance(value, list | tuple) else value  # type: ignore[reportUnknownArgumentType]


def mask(url: str) -> str:
    """Hide the password in a database address."""
    parts = urlsplit(url)
    if parts.password is None:
        return url
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    user = f"{parts.username}:" if parts.username else ":"
    return urlunsplit(parts._replace(netloc=f"{user}****@{host}"))


def _shown(f: Field, value: Any) -> Any:
    return mask(value) if f.secret and isinstance(value, str) else value


def describe(
    settings: Settings, saved: dict[str, dict[str, Any]], started: Snapshot
) -> list[FieldState]:
    states: list[FieldState] = []
    for f in FIELDS:
        running = read_value(settings, f.key)
        if f.key == "storage.data_dir":
            running = str(settings.data_dir)
        env = f.env_name if f.env_name in os.environ else None
        in_file = f.name in saved.get(f.section, {})
        stored = saved.get(f.section, {}).get(f.name)
        chosen = _plain(stored) if in_file and env is None else _plain(running)
        source = "environment" if env else ("saved" if in_file else "default")
        pending = (
            not f.live and in_file and env is None and chosen != started.values.get(f.key, chosen)
        )
        states.append(
            FieldState(f, _shown(f, chosen), _shown(f, _plain(running)), source, pending, env)
        )
    return states


def check_changes(
    settings: Settings, saved: dict[str, dict[str, Any]], changes: dict[str, Any]
) -> dict[str, Any]:
    """Validate what people typed. Returns the values to save, or raises with a plain reason."""
    accepted: dict[str, Any] = {}
    for key, raw in changes.items():
        f = BY_KEY.get(key)
        if f is None:
            raise InvalidInput(f"{key} is not a setting you can change here.")
        if f.env_name in os.environ:
            raise InvalidInput(
                f"“{f.label}” is set by the {f.env_name} environment variable, "
                "so it cannot be changed here."
            )
        value = _clean(f, raw)
        if f.secret and value == mask(str(read_value(settings, f.key))):
            continue  # the masked text came back unchanged
        accepted[key] = value
    _check_together(settings, saved, accepted)
    return accepted


def _clean(f: Field, raw: Any) -> Any:
    label = f"“{f.label}”"
    if f.kind == "bool":
        if not isinstance(raw, bool):
            raise InvalidInput(f"{label} must be on or off.")
        return raw
    if f.kind == "int":
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise InvalidInput(f"{label} must be a whole number.")
        low, high = f.minimum, f.maximum
        if (low is not None and raw < low) or (high is not None and raw > high):
            raise InvalidInput(f"{label} must be between {low:,} and {high:,}.")
        return raw
    if f.kind == "paths":
        if not isinstance(raw, list):
            raise InvalidInput(f"{label} must be a list of folders.")
        return [_folder(str(p), label) for p in raw if str(p).strip()]  # type: ignore[reportUnknownVariableType]
    text = str(raw).strip()
    if f.kind == "choice":
        allowed = {o.value for o in f.options}
        if text not in allowed and not (f.allow_other and text):
            raise InvalidInput(f"{label} must be one of the choices shown.")
        if f.key == "server.host" and not _HOST.match(text):
            raise InvalidInput(f"{label} is not a valid address.")
        if text in allowed:
            return text
        return _clean_text(f, text)
    return _clean_text(f, text)


def _folder(raw: str, label: str) -> str:
    path = Path(raw.strip()).expanduser()
    if not path.is_dir():
        raise InvalidInput(f"{label}: {raw.strip()} is not a folder on this computer.")
    return str(path)


def _clean_text(f: Field, text: str) -> str:
    label = f"“{f.label}”"
    if f.key == "server.public_url" and text:
        parts = urlsplit(text)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise InvalidInput(f"{label} should start with http:// or https://.")
        return text.rstrip("/")
    if f.key == "database.url":
        if not text.startswith(("sqlite:///", "postgresql://", "postgres://")):
            raise InvalidInput(
                f"{label} should start with sqlite:/// or postgresql://. "
                "Leave it as it is to keep the built-in database."
            )
        return text
    if f.key == "storage.data_dir":
        if not text:
            raise InvalidInput(f"{label} cannot be empty.")
        return _writable_folder(text, label)
    return text


def _writable_folder(raw: str, label: str) -> str:
    path = Path(raw).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".katib-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        raise InvalidInput(f"{label}: Katib cannot write to {raw}.") from None
    return str(path)


def _check_together(
    settings: Settings, saved: dict[str, dict[str, Any]], accepted: dict[str, Any]
) -> None:
    """Run the same rules the server applies at startup, on the settings as they would be then."""
    candidate: dict[str, dict[str, Any]] = {
        name: dict(getattr(settings, name).model_dump()) for name in Settings.model_fields
    }
    for section, values in saved.items():
        for name, value in values.items():
            key = f"{section}.{name}"
            if key in BY_KEY and BY_KEY[key].env_name not in os.environ:
                candidate.setdefault(section, {})[name] = value
    for key, value in accepted.items():
        section, name = key.split(".")
        if key == "storage.data_dir":
            continue
        candidate[section][name] = value
    try:
        Settings.model_validate(candidate)
    except ValidationError as err:
        message = str(err.errors()[0]["msg"])
        raise InvalidInput(message.removeprefix("Value error, ")) from err
