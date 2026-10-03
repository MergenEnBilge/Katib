import sys
import types
from pathlib import Path

import pytest

from katib.config import Settings
from katib.desktop import window
from katib.desktop.window import DesktopUnavailable, remote_address, run_desktop
from katib.server import instance

RUNNING = instance.ServerInfo(
    pid=1, url="http://127.0.0.1:8420", host="127.0.0.1", port=8420, version="0", token="t"
)


class FakeWindow:
    """Stands in for the pywebview window handle ``create_window`` returns."""

    def __init__(self) -> None:
        self.loaded: str | None = None

    def load_url(self, url: str) -> None:
        self.loaded = url


def fake_webview(on_start: object) -> tuple[types.SimpleNamespace, dict[str, object]]:
    """A ``webview`` module whose window records the launcher it was given and, once started,
    runs ``on_start(api, window)`` -- standing in for whatever the person clicks."""
    seen: dict[str, object] = {}

    def create_window(title: str, **kwargs: object) -> FakeWindow:
        seen["title"], seen["html"], seen["api"] = title, kwargs.get("html"), kwargs.get("js_api")
        seen["window"] = FakeWindow()
        return seen["window"]  # type: ignore[return-value]

    def start() -> None:
        on_start(seen["api"], seen["window"])  # type: ignore[operator]

    return types.SimpleNamespace(create_window=create_window, start=start), seen


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


def test_the_window_uses_a_server_that_is_already_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[bool] = []
    monkeypatch.setattr(window.instance, "find_running", lambda _d: RUNNING)
    monkeypatch.setattr(window, "start_server", lambda: started.append(True))

    fake, seen = fake_webview(lambda api, _w: api.open_local())
    monkeypatch.setitem(sys.modules, "webview", fake)
    run_desktop(Settings(storage={"data_dir": str(tmp_path)}))

    assert seen["window"].loaded == RUNNING.url  # type: ignore[union-attr]
    assert started == []


def test_the_window_starts_the_server_when_none_is_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[bool] = []
    monkeypatch.setattr(window.instance, "find_running", lambda _d: None)
    monkeypatch.setattr(window.instance, "wait_for", lambda _d, _s: RUNNING)
    monkeypatch.setattr(window, "start_server", lambda: started.append(True))

    fake, seen = fake_webview(lambda api, _w: api.open_local())
    monkeypatch.setitem(sys.modules, "webview", fake)
    run_desktop(Settings(storage={"data_dir": str(tmp_path)}))

    assert started == [True]
    assert seen["window"].loaded == RUNNING.url  # type: ignore[union-attr]


def test_a_server_that_never_comes_up_says_where_to_look(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(window.instance, "find_running", lambda _d: None)
    monkeypatch.setattr(window.instance, "wait_for", lambda _d, _s: None)
    monkeypatch.setattr(window, "start_server", lambda: None)
    result: dict[str, object] = {}

    fake, seen = fake_webview(lambda api, _w: result.update(api.open_local()))
    monkeypatch.setitem(sys.modules, "webview", fake)
    run_desktop(Settings(storage={"data_dir": str(tmp_path)}))

    assert result["ok"] is False
    assert "server.log" in str(result["error"])
    assert seen["window"].loaded is None  # type: ignore[union-attr]


def test_closing_the_window_leaves_the_server_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stopped: list[bool] = []
    monkeypatch.setattr(window.instance, "find_running", lambda _d: RUNNING)
    monkeypatch.setattr(window.instance, "stop", lambda *_a: stopped.append(True) or True)

    fake, _seen = fake_webview(lambda api, _w: api.open_local())
    monkeypatch.setitem(sys.modules, "webview", fake)
    run_desktop(Settings(storage={"data_dir": str(tmp_path)}))

    assert stopped == []


def test_the_launcher_can_stop_this_computers_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stopped: list[bool] = []
    monkeypatch.setattr(window.instance, "find_running", lambda _d: RUNNING)
    monkeypatch.setattr(window.instance, "stop", lambda *_a: stopped.append(True) or True)
    result: dict[str, object] = {}

    fake, _seen = fake_webview(lambda api, _w: result.update(api.stop_local()))
    monkeypatch.setitem(sys.modules, "webview", fake)
    run_desktop(Settings(storage={"data_dir": str(tmp_path)}))

    assert result == {"ok": True}
    assert stopped == [True]


def test_connecting_to_a_server_never_starts_one_of_your_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[bool] = []
    monkeypatch.setattr(window, "start_server", lambda: started.append(True))

    def click_connect(api: object, _w: FakeWindow) -> None:
        assert api.open_remote("team.example.com") == {"ok": True}  # type: ignore[attr-defined]

    fake, seen = fake_webview(click_connect)
    monkeypatch.setitem(sys.modules, "webview", fake)
    run_desktop(Settings(storage={"data_dir": str(tmp_path)}))

    assert seen["window"].loaded == "http://team.example.com"  # type: ignore[union-attr]
    assert started == []


def test_connecting_with_nothing_typed_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def click_connect(api: object, _w: FakeWindow) -> None:
        assert api.open_remote("   ")["ok"] is False  # type: ignore[attr-defined]

    fake, seen = fake_webview(click_connect)
    monkeypatch.setitem(sys.modules, "webview", fake)
    run_desktop(Settings(storage={"data_dir": str(tmp_path)}))

    assert seen["window"].loaded is None  # type: ignore[union-attr]


def test_the_launcher_remembers_the_last_server_you_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katib.config import write_remote_choice

    write_remote_choice("http://team.example.com")
    fake, seen = fake_webview(lambda _api, _w: None)
    monkeypatch.setitem(sys.modules, "webview", fake)
    run_desktop(Settings(storage={"data_dir": str(tmp_path)}))

    assert "team.example.com" in str(seen["html"])


def test_a_remembered_address_cannot_break_out_of_the_launcher_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A remembered address is untrusted -- it was typed once and saved to disk. It must not be
    able to inject markup into a page whose script can call back into pywebview.api."""
    from katib.config import write_remote_choice

    write_remote_choice('"><script>evil()</script>')
    fake, seen = fake_webview(lambda _api, _w: None)
    monkeypatch.setitem(sys.modules, "webview", fake)
    run_desktop(Settings(storage={"data_dir": str(tmp_path)}))

    assert "<script>evil()</script>" not in str(seen["html"])


def test_the_launcher_credits_the_author(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake, seen = fake_webview(lambda _api, _w: None)
    monkeypatch.setitem(sys.modules, "webview", fake)
    run_desktop(Settings(storage={"data_dir": str(tmp_path)}))

    assert "M. Abdullah K. Mughal (MergenEnBilge)" in str(seen["html"])


def test_missing_toolkit_gives_a_plain_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "webview", None)
    with pytest.raises(DesktopUnavailable, match="uv sync --extra desktop"):
        run_desktop(Settings(storage={"data_dir": str(tmp_path)}))


@pytest.mark.parametrize(
    "typed", ["file:///C:/Windows/win.ini", "javascript:alert(1)", "ftp://example.com", "http://"]
)
def test_the_window_opens_only_web_addresses(typed: str) -> None:
    assert remote_address(typed) == ""


def test_a_remote_page_cannot_use_the_windows_own_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stopped: list[bool] = []
    running = instance.ServerInfo(
        pid=1, url="http://127.0.0.1:8420", host="127.0.0.1", port=8420, version="0", token="t"
    )
    monkeypatch.setattr(window.instance, "find_running", lambda _d: running)
    monkeypatch.setattr(window.instance, "stop", lambda *_a: stopped.append(True) or True)
    results: dict[str, object] = {}

    class FakeWindow:
        def load_url(self, url: str) -> None:
            results["loaded"] = url

    def visit_a_remote_server_then_misbehave(api: object) -> None:
        assert api.open_remote("team.example.com") == {"ok": True}  # type: ignore[attr-defined]
        # From here on, the page in the window is the remote server's.
        results["stop"] = api.stop_local()  # type: ignore[attr-defined]
        results["status"] = api.status()  # type: ignore[attr-defined]
        results["open"] = api.open_remote("evil.example")  # type: ignore[attr-defined]

    seen: dict[str, object] = {}

    def create_window(_title: str, **kwargs: object) -> FakeWindow:
        seen["api"] = kwargs["js_api"]
        return FakeWindow()

    fake = types.SimpleNamespace(
        create_window=create_window,
        start=lambda: visit_a_remote_server_then_misbehave(seen["api"]),
    )
    monkeypatch.setitem(sys.modules, "webview", fake)
    run_desktop(Settings(storage={"data_dir": str(tmp_path)}))

    assert results["stop"] == {"ok": False, "error": "Only Katib's own start page can do this."}
    assert results["status"] == {"running": False, "url": ""}
    assert results["open"]["ok"] is False  # type: ignore[index]
    assert results["loaded"] == "http://team.example.com"
    assert stopped == []
