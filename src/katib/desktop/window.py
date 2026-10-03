"""Katib in its own window: a client, like a browser tab, for a server that runs on its own.

The window opens on a small launcher. "Open my own" finds the Katib server already running for
this computer's data folder, or starts one in the background, and shows it. That server does not
belong to the window: it keeps running after the window closes, so phones and colleagues keep
their connection, and it lives on in the system tray until someone stops it there, here, or with
`katib stop`. "Connect" opens a Katib someone else is running instead, exactly as a browser would.

If the server the window is showing goes away -- stopped from the tray, or a remote one that
stops answering -- the window comes back to the launcher and says so, rather than leaving a dead
page with no way back.
"""

from __future__ import annotations

import html
import os
import subprocess
import threading
import time
from typing import Any
from urllib.parse import urlsplit

from katib.config import Settings, read_remote_choice, write_remote_choice
from katib.desktop.autostart import server_command
from katib.desktop.notice import open_path
from katib.server import instance

START_TIMEOUT_SECONDS = 30
#: How long to wait for a server that is finishing a job before it stops.
STOP_TIMEOUT_SECONDS = 120
#: How often the window checks that the server it shows is still there.
WATCH_SECONDS = 3.0
#: A remote server gets a few missed checks before the window gives up on it: networks blink.
REMOTE_MISSES = 3

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
  main {{ width: 360px; }}
  h1 {{ font-size: 1.1rem; font-weight: 600; margin: 0 0 1.25rem; }}
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
  button.quiet {{ background: transparent; color: #edefea; margin-top: 0.5rem; }}
  button.link {{
    width: auto;
    padding: 0;
    border: 0;
    background: none;
    color: #4bcb8b;
    font-weight: 400;
    font-size: 0.8rem;
    text-decoration: underline;
  }}
  button:disabled {{ opacity: 0.6; cursor: default; }}
  input {{
    padding: 0.55rem;
    border-radius: 6px;
    border: 1px solid #2a322b;
    background: #161a16;
    color: #edefea;
    margin: 0.75rem 0 0.5rem;
  }}
  p {{ font-size: 0.8rem; color: #9aa39b; margin: 0.4rem 0; }}
  #status {{ min-height: 1.2em; }}
  .error {{ color: #e2734f; min-height: 1.2em; }}
  .notice {{
    color: #edefea;
    background: #2a2216;
    border: 1px solid #5a4a2a;
    border-radius: 6px;
    padding: 0.6rem 0.75rem;
    margin: 0 0 1rem;
  }}
  hr {{ border: 0; border-top: 1px solid #2a322b; margin: 1.25rem 0; }}
  footer {{ margin-top: 1.5rem; font-size: 0.75rem; color: #6f786f; }}
  footer a {{ color: #4bcb8b; }}
</style>
<main>
  <h1>Katib</h1>
  <p class="notice" id="notice" {notice_hidden}>{notice}</p>
  <p id="status">Checking this computer...</p>
  <button id="open" onclick="openLocal()">Open my own</button>
  <button id="stop" class="quiet" onclick="stopLocal()" hidden>
    Stop the server on this computer
  </button>
  <p class="error" id="local-error"></p>
  <p><button class="link" onclick="openLog()">Show the server's log</button></p>
  <hr>
  <p>Or connect to a Katib someone else is running:</p>
  <input id="url" placeholder="katib.example.com" value="{remote}">
  <button id="connect" class="quiet" onclick="openRemote()">Connect</button>
  <p class="error" id="error"></p>
  <footer>
    Built by
    <a href="https://github.com/MergenEnBilge" target="_blank"
      >M. Abdullah K. Mughal (MergenEnBilge)</a>
  </footer>
</main>
<script>
  function show(state) {{
    document.getElementById('status').textContent = state.running
      ? 'Running on this computer at ' + state.url + '.'
      : 'Not running on this computer. Opening it starts it.';
    document.getElementById('open').textContent =
      state.running ? 'Open my own' : 'Start and open my own';
    document.getElementById('stop').hidden = !state.running;
  }}
  function refresh() {{
    pywebview.api.status().then(show).catch(function () {{
      document.getElementById('status').textContent = 'Could not check this computer.';
    }});
  }}
  window.addEventListener('pywebviewready', refresh);
  function say(id, text) {{ document.getElementById(id).textContent = text || ''; }}
  function openLocal() {{
    var open = document.getElementById('open');
    open.disabled = true;
    open.textContent = 'Starting...';
    say('local-error');
    pywebview.api.open_local().then(function (result) {{
      if (!result.ok) {{
        say('local-error', result.error);
        open.disabled = false;
        refresh();
      }}
    }});
  }}
  function stopLocal() {{
    var stop = document.getElementById('stop');
    stop.disabled = true;
    stop.textContent = 'Stopping... (any job still running finishes first)';
    say('local-error');
    pywebview.api.stop_local().then(function (result) {{
      stop.disabled = false;
      stop.textContent = 'Stop the server on this computer';
      say('local-error', result.ok ? '' : result.error);
      if (result.ok) say('status', 'Stopped.');
      refresh();
    }});
  }}
  function openLog() {{
    pywebview.api.open_log().then(function (result) {{
      if (!result.ok) say('local-error', result.error);
    }});
  }}
  function openRemote() {{
    say('error');
    pywebview.api.open_remote(document.getElementById('url').value).then(function (result) {{
      if (!result.ok) say('error', result.error);
    }});
  }}
</script>
"""


class DesktopUnavailable(Exception):
    """The window toolkit is not installed."""


def launcher_page(notice: str = "") -> str:
    return LAUNCHER_HTML.format(
        remote=html.escape(read_remote_choice()),
        notice=html.escape(notice),
        notice_hidden="" if notice else "hidden",
    )


def remote_address(typed: str) -> str:
    """What to actually open for something typed into the launcher's address field, or an empty
    string if there is nothing usable there. A bare host such as ``katib.example.com`` is assumed
    to be plain http, same as a browser's address bar with no scheme typed."""
    typed = typed.strip()
    if not typed:
        return ""
    if "://" not in typed:
        typed = f"http://{typed}"
    parts = urlsplit(typed)
    # Only web addresses: anything else (file://, javascript:...) has no business in this window.
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return ""
    try:
        parts.port  # noqa: B018 -- "javascript:alert(1)" arrives here as a host with a bad port
    except ValueError:
        return ""
    return typed


def start_server() -> subprocess.Popen[Any]:
    """Start the background server, detached, so closing this window never takes it down."""
    options: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        options["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        )
    else:
        options["start_new_session"] = True
    return subprocess.Popen(server_command(), **options)  # noqa: S603 -- our own program


def ensure_running(settings: Settings) -> instance.ServerInfo | None:
    """The server for this data folder, started first if it is not running yet. Gives up as soon
    as a server it started has exited, rather than waiting out the whole timeout."""
    running = instance.find_running(settings.data_dir)
    if running is not None:
        return running
    started = start_server()
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        found = instance.find_running(settings.data_dir)
        if found is not None:
            return found
        # Exiting with 0 means another server won the race for the folder; keep looking for it.
        if started.poll() not in (None, 0):
            return None
        time.sleep(0.2)
    return None


def run_desktop(settings: Settings) -> None:
    try:
        import webview  # pyright: ignore[reportMissingImports]
    except ImportError as err:
        raise DesktopUnavailable(
            "The desktop window needs an extra package. Install it with: uv sync --extra desktop"
        ) from err

    log_path = settings.data_dir / "logs" / "server.log"
    # pywebview hands `js_api` to whatever page the window shows -- including a Katib on someone
    # else's server once the window has gone there. So the API answers only while the window
    # shows its own launcher; only this code below changes that, never a page.
    state: dict[str, Any] = {"launcher": True, "showing": None, "local": False}
    refused: dict[str, object] = {"ok": False, "error": "Only Katib's own start page can do this."}
    closed = threading.Event()

    def show(url: str, *, local: bool) -> None:
        assert window is not None
        state.update(launcher=False, showing=url, local=local)
        window.load_url(url)

    def back_to_launcher(notice: str) -> None:
        assert window is not None
        state.update(launcher=True, showing=None, local=False)
        window.load_html(launcher_page(notice))

    def watch() -> None:
        """Bring the window back to the launcher when the server it shows goes away."""
        misses = 0
        while not closed.wait(WATCH_SECONDS):
            url = state["showing"]
            if url is None:
                misses = 0
                continue
            if state["local"]:
                gone = instance.find_running(settings.data_dir) is None
                if gone:
                    back_to_launcher(
                        "Katib's server on this computer stopped. Start it again below, "
                        "or show its log to see why."
                    )
                continue
            misses = 0 if instance.answers(url) else misses + 1
            if misses >= REMOTE_MISSES:
                misses = 0
                back_to_launcher(
                    f"{url} stopped answering. It may have been stopped, or this computer "
                    "lost its connection to it."
                )

    class Api:
        def status(self) -> dict[str, object]:
            if not state["launcher"]:
                return {"running": False, "url": ""}
            running = instance.find_running(settings.data_dir)
            return {"running": running is not None, "url": running.url if running else ""}

        def open_local(self) -> dict[str, object]:
            if not state["launcher"]:
                return refused
            running = ensure_running(settings)
            if running is None:
                return {
                    "ok": False,
                    "error": "Katib's server did not start. Show its log to see why.",
                }
            show(running.url, local=True)
            return {"ok": True}

        def stop_local(self) -> dict[str, object]:
            if not state["launcher"]:
                return refused
            running = instance.find_running(settings.data_dir)
            if running is None or instance.stop(running, settings.data_dir, STOP_TIMEOUT_SECONDS):
                return {"ok": True}
            return {
                "ok": False,
                "error": "Katib is still finishing a job. It stops as soon as that is done.",
            }

        def open_log(self) -> dict[str, object]:
            if not state["launcher"]:
                return refused
            if open_path(log_path):
                return {"ok": True}
            return {"ok": False, "error": f"There is no log yet. It will be at {log_path}."}

        def open_remote(self, typed: str) -> dict[str, object]:
            if not state["launcher"]:
                return refused
            url = remote_address(typed)
            if not url:
                return {"ok": False, "error": "Type a web address, such as katib.example.com."}
            if not instance.answers(url, timeout=5):
                return {
                    "ok": False,
                    "error": f"Nothing that looks like Katib answered at {url}. Check the "
                    "address, and that this computer is on the same network.",
                }
            write_remote_choice(url)
            show(url, local=False)
            return {"ok": True}

    window = webview.create_window(
        "Katib", html=launcher_page(), js_api=Api(), width=1400, height=900
    )
    assert window is not None  # only None when a window already exists, which none does here
    watcher = threading.Thread(target=watch, name="katib-window-watch", daemon=True)
    watcher.start()
    try:
        # Nothing to shut down afterwards: the server is not this window's to stop.
        webview.start()
    finally:
        closed.set()
