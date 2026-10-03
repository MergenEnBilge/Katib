"""Katib's server in the background, with an icon in the system tray while it runs.

The icon is how someone knows the server is still there after they close the window, and how they
stop it: there is no hidden process to hunt for. The menu runs on the main thread, as macOS
requires, and the server runs beside it. If this desktop has no tray (GNOME without its
AppIndicator extension, say) the server still runs, and the Katib window offers a Stop button.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from katib.config import Settings, load_settings
from katib.desktop import autostart
from katib.desktop.notice import open_path, show_error
from katib.server.run import AlreadyRunning, DidNotStart, ManagedServer
from katib.services import setup_code

log = logging.getLogger(__name__)

REPO_URL = "https://github.com/MergenEnBilge/Katib"
ICON = Path(__file__).resolve().parent.parent / "static" / "icon-192.png"


def log_to_file(settings: Settings) -> Path:
    """A background program has no console, so its log goes to the data folder."""
    folder = settings.data_dir / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "server.log"
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    return path


def window_command() -> list[str] | None:
    """What opens the Katib window, or None when only a browser can show it."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        sibling = exe.with_name("Katib.exe" if sys.platform == "win32" else "Katib")
        return [str(sibling)] if sibling.exists() else None
    try:
        import webview  # noqa: F401  # pyright: ignore[reportMissingImports, reportUnusedImport]
    except ImportError:
        return None
    return [sys.executable, "-m", "katib", "app"]


def open_window(url: str) -> None:
    command = window_command()
    if command is None:
        webbrowser.open(url)
        return
    subprocess.Popen(command, close_fds=True)  # noqa: S603 -- our own program, no user input


def _image() -> Any:
    from PIL import Image, ImageDraw

    if ICON.is_file():
        return Image.open(ICON)
    # A plain mark for a development checkout that has not built the interface yet.
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(image).rounded_rectangle((4, 4, 60, 60), radius=12, fill=(47, 163, 102, 255))
    return image


def _run_tray(server: ManagedServer, url: str, log_path: Path) -> bool:
    """Show the icon until the server stops. False if this desktop has no tray to show it in."""
    try:
        import pystray  # pyright: ignore[reportMissingImports]
    except ImportError:
        return False

    def stop_server(icon: Any, _item: Any) -> None:
        log.info("Stopping, as asked from the tray.")
        server.stop()
        icon.stop()

    def toggle_autostart(icon: Any, item: Any) -> None:
        try:
            autostart.set_enabled(not item.checked)
        except OSError as err:
            log.warning("Could not change starting at sign-in.", exc_info=True)
            icon.notify(f"Could not change that: {err}", "Katib")

    def show_log(icon: Any, _item: Any) -> None:
        if not open_path(log_path):
            icon.notify(f"The log is at {log_path}", "Katib")

    def finish_setup() -> None:
        webbrowser.open(setup_code.setup_link(url, setup_code.pending(server.data_dir)))

    menu = pystray.Menu(
        pystray.MenuItem(f"Katib is running at {url}", lambda: None, enabled=False),
        pystray.MenuItem("Open Katib", lambda: open_window(url), default=True),
        # Only while the server waits for its first administrator: the code is filled in.
        pystray.MenuItem(
            "Finish setting up Katib",
            finish_setup,
            visible=lambda _item: setup_code.pending(server.data_dir) is not None,  # pyright: ignore[reportArgumentType]
        ),
        pystray.MenuItem("Open in my browser", lambda: webbrowser.open(url)),
        pystray.MenuItem(
            "Share with phones and colleagues", lambda: webbrowser.open(f"{url}/settings")
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Start when I sign in",
            toggle_autostart,
            checked=lambda _item: autostart.is_enabled(),
        ),
        pystray.MenuItem("Show the log", show_log),
        pystray.MenuItem("About Katib", lambda: webbrowser.open(REPO_URL)),
        pystray.Menu.SEPARATOR,
        # A submenu is the confirmation: stopping cuts off every phone and browser connected.
        pystray.MenuItem(
            "Stop the server",
            pystray.Menu(
                pystray.MenuItem(
                    "Phones and browsers using it will lose their connection",
                    lambda: None,
                    enabled=False,
                ),
                pystray.MenuItem("Stop it now", stop_server),
            ),
        ),
    )
    icon = pystray.Icon("katib", _image(), f"Katib, running at {url}", menu)

    def watch(icon: Any) -> None:
        # pystray runs this on a thread of its own. A server stopped some other way -- from the
        # window, `katib stop`, or a restart -- takes the icon down with it, so the icon never
        # claims a server that is no longer there.
        icon.visible = True
        server.wait_until_stopped()
        icon.stop()

    try:
        icon.run(setup=watch)
    except Exception:  # noqa: BLE001 -- any failure to draw a tray icon is "no tray"
        log.warning("No system tray here, so Katib runs without an icon.", exc_info=True)
        return False
    return True


def run(settings: Settings | None = None, *, quiet: bool = False) -> int:
    """Serve with a tray icon until stopped.

    `quiet` is for being started without anyone asking just now -- by the window, or at sign-in.
    Started by hand, from the Start menu say, a problem gets a message on screen as well as in
    the log, and a server that is already running is opened rather than started twice.
    """
    settings = settings or load_settings()
    path = log_to_file(settings)
    try:
        return _serve_with_tray(settings, path, quiet=quiet)
    except Exception as err:
        log.exception("Katib's server stopped because of an error.")
        if not quiet:
            show_error(
                "Katib stopped",
                f"Katib's server stopped because of an error: {err}\n\nThe details are in {path}.",
            )
        return 1


def _serve_with_tray(settings: Settings, path: Path, *, quiet: bool) -> int:
    server = ManagedServer(settings, any_port=True)
    try:
        info = server.start()
    except AlreadyRunning as err:
        log.info("%s", err)
        if not quiet and err.url:
            open_window(err.url)
        return 0
    except DidNotStart as err:
        log.error("%s See %s", err, path)
        if not quiet:
            show_error("Katib could not start", f"{err}\n\nThe details are in {path}.")
        return 1
    if not _run_tray(server, info.url, path):
        server.wait_until_stopped()
    server.stop()
    server.wait()
    log.info("Katib's server has stopped.")
    return 0
