import socket
import sys
import types
import urllib.request
from pathlib import Path

import pytest
import uvicorn

from katib.config import Settings
from katib.desktop.window import (
    DesktopUnavailable,
    free_port,
    remote_address,
    run_desktop,
    window_host,
)


class FakeWindow:
    """Stands in for the pywebview window handle ``create_window`` returns."""

    def __init__(self) -> None:
        self.loaded: str | None = None

    def load_url(self, url: str) -> None:
        self.loaded = url


def fake_webview(on_start: object) -> types.SimpleNamespace:
    """A ``webview`` module whose window records the launcher it was given and, once started,
    runs ``on_start(api, window)`` -- standing in for whatever the person clicks in the launcher."""
    seen: dict[str, object] = {}

    def create_window(title: str, **kwargs: object) -> FakeWindow:
        seen["title"], seen["html"], seen["api"] = title, kwargs.get("html"), kwargs.get("js_api")
        seen["window"] = FakeWindow()
        return seen["window"]  # type: ignore[return-value]

    def start() -> None:
        on_start(seen["api"], seen["window"])  # type: ignore[operator]

    return types.SimpleNamespace(create_window=create_window, start=start), seen


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


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("", ""),
        ("   ", ""),
        ("katib.example.com", "http://katib.example.com"),
        ("http://katib.example.com", "http://katib.example.com"),
        ("https://katib.example.com:8420", "https://katib.example.com:8420"),
    ],
)
def test_remote_address_fills_in_a_scheme_like_a_browser_bar_would(
    typed: str, expected: str
) -> None:
    assert remote_address(typed) == expected


def test_opening_your_own_starts_a_server_and_stops_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checked: dict[str, str] = {}

    def click_open_local(api: object, window: FakeWindow) -> None:
        api.open_local()  # type: ignore[attr-defined]
        url = window.loaded
        assert url is not None
        with urllib.request.urlopen(f"{url}/api/v1/health", timeout=5) as res:
            checked["health"] = res.read().decode()
        checked["url"] = url

    fake, _seen = fake_webview(click_open_local)
    monkeypatch.setitem(sys.modules, "webview", fake)

    run_desktop(Settings(storage={"data_dir": str(tmp_path)}))

    assert checked["url"].startswith("http://127.0.0.1:")
    assert '"status":"ok"' in checked["health"]
    with pytest.raises(OSError):
        urllib.request.urlopen(f"{checked['url']}/api/v1/health", timeout=2)


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

    def click_open_local(api: object, window: FakeWindow) -> None:
        api.open_local()  # type: ignore[attr-defined]

    fake, _seen = fake_webview(click_open_local)
    monkeypatch.setitem(sys.modules, "webview", fake)

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

        def click_open_local(api: object, window: FakeWindow) -> None:
            api.open_local()  # type: ignore[attr-defined]

        fake, _seen = fake_webview(click_open_local)
        monkeypatch.setitem(sys.modules, "webview", fake)

        settings = Settings(storage={"data_dir": str(tmp_path)}, server={"port": taken})
        run_desktop(settings)

        assert settings.server.port != taken


def test_connecting_to_a_server_never_starts_one_of_your_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def click_connect(api: object, window: FakeWindow) -> None:
        result = api.open_remote("team.example.com")  # type: ignore[attr-defined]
        assert result == {"ok": True}

    fake, seen = fake_webview(click_connect)
    monkeypatch.setitem(sys.modules, "webview", fake)

    run_desktop(Settings(storage={"data_dir": str(tmp_path)}))

    assert seen["window"].loaded == "http://team.example.com"  # type: ignore[union-attr]


def test_connecting_with_nothing_typed_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def click_connect(api: object, window: FakeWindow) -> None:
        result = api.open_remote("   ")  # type: ignore[attr-defined]
        assert result["ok"] is False

    fake, seen = fake_webview(click_connect)
    monkeypatch.setitem(sys.modules, "webview", fake)

    run_desktop(Settings(storage={"data_dir": str(tmp_path)}))

    assert seen["window"].loaded is None  # type: ignore[union-attr]


def test_the_launcher_remembers_the_last_server_you_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katib.config import write_remote_choice

    monkeypatch.setenv("KATIB_CONFIG_DIR", str(tmp_path / "config"))
    write_remote_choice("http://team.example.com")

    fake, seen = fake_webview(lambda api, window: None)
    monkeypatch.setitem(sys.modules, "webview", fake)

    run_desktop(Settings(storage={"data_dir": str(tmp_path / "data")}))

    assert "team.example.com" in str(seen["html"])


def test_missing_toolkit_gives_a_plain_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "webview", None)
    with pytest.raises(DesktopUnavailable, match="uv sync --extra desktop"):
        run_desktop(Settings(storage={"data_dir": str(tmp_path)}))
