import sys
import types
import urllib.request
from pathlib import Path

import pytest

from katib.config import Settings
from katib.desktop.window import DesktopUnavailable, free_port, run_desktop


def test_free_port_is_usable() -> None:
    assert 1024 <= free_port() <= 65535


def test_window_shows_a_running_server_and_stops_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, str] = {}

    def create_window(title: str, url: str, **_: object) -> None:
        seen["title"], seen["url"] = title, url

    def start() -> None:
        with urllib.request.urlopen(f"{seen['url']}/api/v1/health", timeout=5) as res:
            seen["health"] = res.read().decode()

    fake = types.SimpleNamespace(create_window=create_window, start=start)
    monkeypatch.setitem(sys.modules, "webview", fake)

    run_desktop(Settings(storage={"data_dir": str(tmp_path)}))

    assert seen["title"] == "Katib"
    assert seen["url"].startswith("http://127.0.0.1:")
    assert '"status":"ok"' in seen["health"]
    with pytest.raises(OSError):
        urllib.request.urlopen(f"{seen['url']}/api/v1/health", timeout=2)


def test_missing_toolkit_gives_a_plain_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "webview", None)
    with pytest.raises(DesktopUnavailable, match="uv sync --extra desktop"):
        run_desktop(Settings(storage={"data_dir": str(tmp_path)}))
