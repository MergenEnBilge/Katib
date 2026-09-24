from pathlib import Path

import pytest
from pydantic import ValidationError

from katib.config import Settings, is_loopback, load_settings


def test_defaults_run_without_a_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    s = load_settings()
    assert s.server.host == "127.0.0.1"
    assert s.server.port == 8420
    assert s.auth.mode == "none"


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.20", "example.com", "::"])
def test_auth_none_refuses_non_loopback(host: str) -> None:
    with pytest.raises(ValidationError, match="loopback"):
        Settings(server={"host": host})


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_auth_none_allows_loopback(host: str) -> None:
    assert Settings(server={"host": host}).server.host == host


def test_local_auth_allows_any_host() -> None:
    s = Settings(server={"host": "0.0.0.0"}, auth={"mode": "local"})
    assert s.server.host == "0.0.0.0"


def test_check_bind_catches_host_changed_after_load() -> None:
    s = Settings()
    s.server.host = "0.0.0.0"
    with pytest.raises(ValueError, match="loopback"):
        s.check_bind()


def test_env_beats_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "katib.toml"
    cfg.write_text("[server]\nport = 9000\n")
    monkeypatch.setenv("KATIB_SERVER__PORT", "9100")
    assert load_settings(cfg).server.port == 9100


def test_file_values_are_read(tmp_path: Path) -> None:
    cfg = tmp_path / "katib.toml"
    cfg.write_text("[server]\nport = 9000\n")
    assert load_settings(cfg).server.port == 9000


def test_missing_explicit_file_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_settings(tmp_path / "nope.toml")


def test_data_dir_placeholder_is_expanded(tmp_path: Path) -> None:
    s = Settings(storage={"data_dir": str(tmp_path)})
    assert s.database_url == f"sqlite:///{tmp_path.as_posix()}/katib.db"


@pytest.mark.parametrize(
    ("host", "expected"),
    [("127.0.0.1", True), ("::1", True), ("localhost", True), ("10.0.0.5", False), ("foo", False)],
)
def test_is_loopback(host: str, expected: bool) -> None:
    assert is_loopback(host) is expected
