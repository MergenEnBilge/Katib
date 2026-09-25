"""Run Katib in its own window instead of a browser tab.

The server still runs, but only on this computer and on a port the system picks, so nothing
else can reach it. Closing the window stops the server.
"""

import socket
import threading
import time

import uvicorn

from katib.api.app import create_app
from katib.config import Settings

START_TIMEOUT_SECONDS = 30


class DesktopUnavailable(Exception):
    """The window toolkit is not installed."""


def free_port() -> int:
    """A port on the loopback address that nothing is using right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def run_desktop(settings: Settings) -> None:
    try:
        import webview
    except ImportError as err:
        raise DesktopUnavailable(
            "The desktop window needs an extra package. Install it with: uv sync --extra desktop"
        ) from err

    port = free_port()
    api = create_app(settings)
    api.state.can_restart = False  # the window would be left pointing at a server that is gone
    server = uvicorn.Server(uvicorn.Config(api, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while not server.started:
        if time.monotonic() > deadline or not thread.is_alive():
            server.should_exit = True
            raise RuntimeError("Katib did not start.")
        time.sleep(0.05)

    webview.create_window("Katib", f"http://127.0.0.1:{port}", width=1400, height=900)
    try:
        webview.start()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
