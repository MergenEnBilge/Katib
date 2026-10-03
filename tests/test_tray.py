import sys
import types
from pathlib import Path

import pytest

from katib.config import Settings
from katib.desktop import autostart, tray
from katib.server import instance
from katib.server.run import ManagedServer


def settings_for(data: Path) -> Settings:
    return Settings(storage={"data_dir": str(data)}, server={"port": 0})


@pytest.mark.slow
def test_the_tray_server_lets_go_of_everything_when_it_stops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def tray_that_is_closed_at_once(server: ManagedServer, url: str, _log: Path) -> bool:
        assert instance.find_running(tmp_path) is not None
        server.stop()
        return True

    monkeypatch.setattr(tray, "_run_tray", tray_that_is_closed_at_once)
    assert tray.run(settings_for(tmp_path)) == 0
    assert instance.lock_is_free(tmp_path)
    assert not (tmp_path / instance.INFO_NAME).exists()
    assert (tmp_path / "logs" / "server.log").is_file()


def test_starting_at_sign_in_on_linux(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert not autostart.is_enabled()
    autostart.enable()
    entry = tmp_path / "autostart" / "katib-server.desktop"
    assert "Exec=" in entry.read_text(encoding="utf-8")
    assert autostart.is_enabled()
    autostart.disable()
    assert not entry.exists()


def test_starting_at_sign_in_on_macos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import plistlib

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    autostart.enable()
    agent = tmp_path / "Library" / "LaunchAgents" / f"{autostart.LAUNCH_AGENT_ID}.plist"
    loaded = plistlib.loads(agent.read_bytes())
    assert loaded["RunAtLoad"] is True and loaded["ProgramArguments"] == autostart.server_command()
    autostart.disable()
    assert not autostart.is_enabled()


def test_starting_at_sign_in_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    store: dict[str, str] = {}

    class Key:
        def __enter__(self) -> "Key":
            return self

        def __exit__(self, *_: object) -> None:
            return None

    def query(_key: Key, name: str) -> tuple[str, int]:
        if name not in store:
            raise FileNotFoundError(name)
        return store[name], 1

    def delete(_key: Key, name: str) -> None:
        if name not in store:
            raise FileNotFoundError(name)
        del store[name]

    fake = types.SimpleNamespace(
        HKEY_CURRENT_USER=0,
        KEY_SET_VALUE=2,
        REG_SZ=1,
        OpenKey=lambda *_a: Key(),
        CreateKey=lambda *_a: Key(),
        QueryValueEx=query,
        SetValueEx=lambda _k, name, _r, _t, value: store.__setitem__(name, value),
        DeleteValue=delete,
    )
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "winreg", fake)
    assert not autostart.is_enabled()
    autostart.enable()
    assert autostart.NAME in store
    assert autostart.is_enabled()
    autostart.disable()
    assert store == {}
