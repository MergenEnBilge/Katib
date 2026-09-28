import socket
import sys
import types
import urllib.request
from pathlib import Path

import pytest
import uvicorn

from katib.config import Settings
from katib.desktop.window import DesktopUnavailable, free_port, run_desktop, window_host


def test_free_port_is_usable() -> None:
    assert 1024 <= free_port("127.0.0.1", 0) <= 65535


def test_free_port_prefers_the_configured_port() -> None:
    port = free_port("127.0.0.1", 0)
    assert free_port("127.0.0.1", port) == port


def test_free_port_falls_back_when_the_configured_port_is_taken() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
        busy.bind(("127.0.0.1", 0))
        taken = busy.getsockname()[1]
        assert free_port("127.0.0.1", taken) != taken


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("127.0.0.1", "127.0.0.1"),
        ("localhost", "127.0.0.1"),
        ("0.0.0.0", "127.0.0.1"),  # noqa: S104
        ("192.168.1.20", "192.168.1.20"),
    ],
)
def test_the_window_points_at_something_that_will_answer(host: str, expected: str) -> None:
    assert window_host(host) == expected


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


def test_sharing_on_the_network_actually_binds_that_address(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bug this pins: the window used to hardcode loopback no matter what Settings said,
    so turning on network sharing was accepted and saved but never actually took effect. A real
    multi-interface bind is not something a test can portably prove, so this checks the one
    thing that decides it: what host uvicorn was actually told to listen on."""
    seen_config: dict[str, str] = {}
    real_config = uvicorn.Config

    def spy_config(app: object, **kwargs: object) -> uvicorn.Config:
        seen_config["host"] = str(kwargs.get("host"))
        return real_config(app, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(uvicorn, "Config", spy_config)
    monkeypatch.setitem(
        sys.modules,
        "webview",
        types.SimpleNamespace(create_window=lambda *a, **k: None, start=lambda: None),
    )

    settings = Settings(
        storage={"data_dir": str(tmp_path)},
        server={"host": "0.0.0.0"},  # noqa: S104
        auth={"mode": "local"},
    )
    run_desktop(settings)

    assert seen_config["host"] == "0.0.0.0"  # noqa: S104


def test_the_share_window_is_told_the_port_actually_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bug this pins: the desktop window used to always pick a random port and never tell
    Settings, so the Share window kept handing out the port from Settings -- one nothing was
    actually listening on."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
        busy.bind(("127.0.0.1", 0))
        taken = busy.getsockname()[1]

        monkeypatch.setitem(
            sys.modules,
            "webview",
            types.SimpleNamespace(create_window=lambda *a, **k: None, start=lambda: None),
        )
        settings = Settings(storage={"data_dir": str(tmp_path)}, server={"port": taken})
        run_desktop(settings)

        assert settings.server.port != taken


def test_missing_toolkit_gives_a_plain_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "webview", None)
    with pytest.raises(DesktopUnavailable, match="uv sync --extra desktop"):
        run_desktop(Settings(storage={"data_dir": str(tmp_path)}))
