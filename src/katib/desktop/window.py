"""Run Katib in its own window instead of a browser tab.

The server binds whatever address Settings, then Sharing says, same as every other way of
running Katib -- "Everyone on my network" works here too. The window itself always talks to the
server over loopback when that reaches it, since that is simplest for the one thing it needs:
showing the page to the person sitting at this computer. Closing the window stops the server.
"""

import socket
import threading
import time

import uvicorn

from katib.api.app import create_app
from katib.config import Settings, is_loopback

START_TIMEOUT_SECONDS = 30


class DesktopUnavailable(Exception):
    """The window toolkit is not installed."""


def free_port(host: str, preferred: int) -> int:
    """The configured port, if nothing on this interface is already using it -- so a device
    told to reach this window at that port, such as from the Share window, actually finds it
    there. Falls back to whatever port is free, same as before Sharing existed, rather than
    refusing to start."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, preferred))
        except OSError:
            probe.bind((host, 0))
        return int(probe.getsockname()[1])


def window_host(host: str) -> str:
    """Where the window itself should point. A wildcard bind answers on loopback too, so the
    window can always reach it there. Only an address pinned to one specific interface (an
    advanced choice) forces the window to use it."""
    return "127.0.0.1" if host == "0.0.0.0" or is_loopback(host) else host


def run_desktop(settings: Settings) -> None:
    try:
        import webview  # pyright: ignore[reportMissingImports]
    except ImportError as err:
        raise DesktopUnavailable(
            "The desktop window needs an extra package. Install it with: uv sync --extra desktop"
        ) from err

    host = settings.server.host
    port = free_port(host, settings.server.port)
    settings.server.port = port  # so the Share window hands out the address that actually answers
    api = create_app(settings)
    api.state.can_restart = False  # the window would be left pointing at a server that is gone
    server = uvicorn.Server(uvicorn.Config(api, host=host, port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while not server.started:
        if time.monotonic() > deadline or not thread.is_alive():
            server.should_exit = True
            raise RuntimeError("Katib did not start.")
        time.sleep(0.05)

    webview.create_window("Katib", f"http://{window_host(host)}:{port}", width=1400, height=900)
    try:
        webview.start()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
