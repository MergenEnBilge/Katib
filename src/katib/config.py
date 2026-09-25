"""Settings loading.

Values come from, in order of priority: environment variables of the form
``KATIB_SECTION__KEY``, the settings saved from inside the app (``settings.json`` in the data
folder), a ``katib.toml`` file, then the defaults below. The defaults are enough to run with no
file at all.
"""

from __future__ import annotations

import contextlib
import ipaddress
import json
import os
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from platformdirs import user_config_path, user_data_path
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8420
    # The address people type when Katib sits behind a proxy, for example https://katib.example.com.
    public_url: str = ""
    # Set when a proxy you control, such as Caddy, is the only way to reach Katib. Katib then
    # believes the proxy about the visitor's address and whether they used HTTPS.
    behind_proxy: bool = False


class AuthSettings(BaseModel):
    mode: Literal["none", "local"] = "none"
    secret_key: str = ""


class DatabaseSettings(BaseModel):
    url: str = "sqlite:///{data_dir}/katib.db"


class StorageSettings(BaseModel):
    backend: Literal["local"] = "local"
    data_dir: str = ""
    allowed_import_roots: list[str] = Field(default_factory=list)


class LimitSettings(BaseModel):
    max_upload_mb: int = 50
    max_image_pixels: int = 200_000_000
    operation_retention_days: int = 30


class MlSettings(BaseModel):
    enabled: bool = False
    # Where the .onnx models for pre-labeling live. Empty means "models" in the data folder.
    models_dir: str = ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KATIB_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    server: ServerSettings = Field(default_factory=ServerSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    limits: LimitSettings = Field(default_factory=LimitSettings)
    ml: MlSettings = Field(default_factory=MlSettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Environment beats the toml file, which arrives as init values.
        return (env_settings, init_settings)

    @model_validator(mode="after")
    def _check_bind(self) -> Settings:
        self.check_bind()
        return self

    def check_bind(self) -> None:
        """Refuse auth mode 'none' on a reachable address. Call again after changing host."""
        if self.auth.mode == "none" and not is_loopback(self.server.host):
            raise ValueError(
                f"Auth mode 'none' only runs on a loopback address, not {self.server.host!r}. "
                "Set auth.mode to 'local' to share Katib on the network."
            )

    @property
    def data_dir(self) -> Path:
        if self.storage.data_dir:
            return Path(self.storage.data_dir).expanduser()
        return user_data_path("katib", appauthor=False)

    @property
    def models_dir(self) -> Path:
        if self.ml.models_dir:
            return Path(self.ml.models_dir).expanduser()
        return self.data_dir / "models"

    @property
    def database_url(self) -> str:
        return self.database.url.replace("{data_dir}", self.data_dir.as_posix())


def is_loopback(host: str) -> bool:
    """True for ``localhost`` and loopback IP literals. Anything else counts as reachable."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


SAVED_FILE = "settings.json"


def config_dir() -> Path:
    """Where the pointer to the data folder lives. `KATIB_CONFIG_DIR` moves it, mostly for tests."""
    override = os.environ.get("KATIB_CONFIG_DIR")
    return Path(override) if override else user_config_path("katib", appauthor=False)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}  # type: ignore[return-value]


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write a file so a crash never leaves half of it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = path.with_suffix(".tmp")
    scratch.write_text(json.dumps(data, indent=2), encoding="utf-8")
    with contextlib.suppress(OSError):  # not every file system has permissions
        scratch.chmod(0o600)
    scratch.replace(path)


def read_data_dir_choice() -> str:
    """The data folder chosen inside the app, or an empty string."""
    return str(_read_json(config_dir() / "location.json").get("data_dir", ""))


def write_data_dir_choice(data_dir: str) -> None:
    _write_json(config_dir() / "location.json", {"data_dir": data_dir})


def read_saved(data_dir: Path) -> dict[str, dict[str, Any]]:
    """Settings saved from inside the app, as {section: {key: value}}."""
    raw = _read_json(data_dir / SAVED_FILE)
    return {s: dict(v) for s, v in raw.items() if isinstance(v, dict)}  # type: ignore[arg-type]


def write_saved(data_dir: Path, values: dict[str, dict[str, Any]]) -> None:
    _write_json(data_dir / SAVED_FILE, values)


def _data_dir_for(file_values: dict[str, Any]) -> Path:
    named = os.environ.get("KATIB_STORAGE__DATA_DIR") or file_values.get("storage", {}).get(
        "data_dir"
    )
    named = named or read_data_dir_choice()
    return Path(named).expanduser() if named else user_data_path("katib", appauthor=False)


def load_settings(path: Path | None = None) -> Settings:
    """Build settings from ``path`` (default ``./katib.toml`` when present) and the environment."""
    file_values: dict[str, Any] = {}
    candidate = path or Path("katib.toml")
    if candidate.is_file():
        with candidate.open("rb") as fh:
            file_values = tomllib.load(fh)
    elif path is not None:
        raise FileNotFoundError(f"Config file not found: {path}")

    chosen = read_data_dir_choice()
    if chosen and not file_values.get("storage", {}).get("data_dir"):
        file_values.setdefault("storage", {})["data_dir"] = chosen
    for section, values in read_saved(_data_dir_for(file_values)).items():
        file_values.setdefault(section, {}).update(values)
    return Settings(**file_values)


@lru_cache
def get_settings() -> Settings:
    return load_settings()
