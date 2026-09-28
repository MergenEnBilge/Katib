"""Run Katib in its own window instead of a browser tab.

The window opens on a small launcher, same idea as a browser's home page: run Katib on this
computer, or type the address of a Katib someone else is already running and open that instead.
Only the first choice starts a server of its own -- connecting elsewhere is exactly what a
browser tab would do, and needs nothing more than the address.

Running one of your own binds whatever address Settings, then Sharing says, same as every other
way of running Katib -- "Everyone on my network" works here too. The window itself always talks
to that server over loopback when that reaches it, since that is simplest for the one thing it
needs: showing the page to the person sitting at this computer. Closing the window stops it.
"""

import socket
import threading
import time

import uvicorn

from katib.api.app import create_app
from katib.config import Settings, is_loopback, read_remote_choice, write_remote_choice

START_TIMEOUT_SECONDS = 30

LAUNCHER_HTML = """<!doctype html>
<meta charset="utf-8">
<title>Katib</title>
<style>
  body {{
    margin: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100vh;
    background: #0b0e0c;
    color: #edefea;
    font-family: system-ui, sans-serif;
  }}
  main {{ width: 320px; }}
  h1 {{ font-size: 1.1rem; font-weight: 600; margin: 0 0 1.5rem; }}
  button, input {{
    width: 100%;
    box-sizing: border-box;
    font-size: 0.95rem;
    font-family: inherit;
  }}
  button {{
    padding: 0.6rem;
    border-radius: 6px;
    border: 1px solid #2a322b;
    background: #2fa366;
    color: #0b0e0c;
    font-weight: 600;
    cursor: pointer;
  }}
  #connect {{ background: transparent; color: #edefea; margin-top: 0.5rem; }}
  input {{
    padding: 0.55rem;
    border-radius: 6px;
    border: 1px solid #2a322b;
    background: #161a16;
    color: #edefea;
    margin: 1rem 0 0.5rem;
  }}
  p {{ font-size: 0.8rem; color: #9aa39b; margin: 1.5rem 0 0.25rem; }}
  #error {{ color: #e2734f; min-height: 1.2em; }}
</style>
<main>
  <h1>Katib</h1>
  <button onclick="openLocal()">Open my own</button>
  <p>Or connect to a server someone else is already running:</p>
  <input id="url" placeholder="katib.example.com" value="{remote}">
  <button id="connect" onclick="openRemote()">Connect</button>
  <p id="error"></p>
</main>
<script>
  function openLocal() {{ pywebview.api.open_local(); }}
  function openRemote() {{
    pywebview.api.open_remote(document.getElementById('url').value).then(function (result) {{
      if (!result.ok) document.getElementById('error').textContent = result.error;
    }});
  }}
</script>
"""


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


def remote_address(typed: str) -> str:
    """What to actually open for something typed into the launcher's address field, or an empty
    string if there is nothing usable there. A bare host such as ``katib.example.com`` is assumed
    to be plain http, same as a browser's address bar with no scheme typed."""
    typed = typed.strip()
    if not typed:
        return ""
    if "://" not in typed:
        typed = f"http://{typed}"
    return typed


def _start_local(settings: Settings) -> tuple[str, uvicorn.Server, threading.Thread]:
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

    return f"http://{window_host(host)}:{port}", server, thread


def run_desktop(settings: Settings) -> None:
    try:
        import webview  # pyright: ignore[reportMissingImports]
    except ImportError as err:
        raise DesktopUnavailable(
            "The desktop window needs an extra package. Install it with: uv sync --extra desktop"
        ) from err

    running: dict[str, object] = {}

    class Api:
        def open_local(self) -> None:
            assert window is not None
            url, server, thread = _start_local(settings)
            running["server"], running["thread"] = server, thread
            window.load_url(url)

        def open_remote(self, typed: str) -> dict[str, object]:
            assert window is not None
            url = remote_address(typed)
            if not url:
                return {"ok": False, "error": "Type an address, such as katib.example.com."}
            write_remote_choice(url)
            window.load_url(url)
            return {"ok": True}

    window = webview.create_window(
        "Katib",
        html=LAUNCHER_HTML.format(remote=read_remote_choice()),
        js_api=Api(),
        width=1400,
        height=900,
    )
    assert window is not None  # only None when a window already exists, which none does here
    try:
        webview.start()
    finally:
        server = running.get("server")
        if server is not None:
            server.should_exit = True  # type: ignore[attr-defined]
            running["thread"].join(timeout=5)  # type: ignore[union-attr]
