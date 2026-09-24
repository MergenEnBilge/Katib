"""Settings loading.

Values come from, in order of priority: environment variables of the form
``KATIB_SECTION__KEY``, a ``katib.toml`` file, then the defaults below. The
defaults are enough to run with no file at all.
"""

from __future__ import annotations

import ipaddress
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from platformdirs import user_data_path
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8420


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


def load_settings(path: Path | None = None) -> Settings:
    """Build settings from ``path`` (default ``./katib.toml`` when present) and the environment."""
    file_values: dict[str, Any] = {}
    candidate = path or Path("katib.toml")
    if candidate.is_file():
        with candidate.open("rb") as fh:
            file_values = tomllib.load(fh)
    elif path is not None:
        raise FileNotFoundError(f"Config file not found: {path}")

    return Settings(**file_values)


@lru_cache
def get_settings() -> Settings:
    return load_settings()
