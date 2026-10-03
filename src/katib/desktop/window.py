"""Katib in its own window: a client, like a browser tab, for a server that runs on its own.

The window opens on a small launcher. "Open my own" finds the Katib server already running for
this computer's data folder, or starts one in the background, and shows it. That server does not
belong to the window: it keeps running after the window closes, so phones and colleagues keep
their connection, and it lives on in the system tray until someone stops it there, here, or with
`katib stop`. "Connect" opens a Katib someone else is running instead, exactly as a browser would.
"""

from __future__ import annotations

import html
import os
import subprocess
from typing import Any

from katib.config import Settings, read_remote_choice, write_remote_choice
from katib.desktop.autostart import server_command
from katib.server import instance

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
  main {{ width: 340px; }}
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
  hr {{ border: 0; border-top: 1px solid #2a322b; margin: 1.25rem 0; }}
  footer {{ margin-top: 1.5rem; font-size: 0.75rem; color: #6f786f; }}
  footer a {{ color: #4bcb8b; }}
</style>
<main>
  <h1>Katib</h1>
  <p id="status">Checking this computer...</p>
  <button id="open" onclick="openLocal()">Open my own</button>
  <button id="stop" class="quiet" onclick="stopLocal()" hidden>
    Stop the server on this computer
  </button>
  <p class="error" id="local-error"></p>
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
      : 'Not running on this computer yet. Opening it starts it.';
    document.getElementById('open').textContent =
      state.running ? 'Open my own' : 'Start and open my own';
    document.getElementById('stop').hidden = !state.running;
  }}
  function refresh() {{ pywebview.api.status().then(show); }}
  window.addEventListener('pywebviewready', refresh);
  function busy(on, text) {{
    var open = document.getElementById('open');
    open.disabled = on;
    if (text) open.textContent = text;
  }}
  function openLocal() {{
    busy(true, 'Starting...');
    pywebview.api.open_local().then(function (result) {{
      if (!result.ok) {{
        document.getElementById('local-error').textContent = result.error;
        busy(false);
        refresh();
      }}
    }});
  }}
  function stopLocal() {{
    document.getElementById('stop').disabled = true;
    pywebview.api.stop_local().then(function (result) {{
      document.getElementById('stop').disabled = false;
      document.getElementById('local-error').textContent = result.ok ? '' : result.error;
      refresh();
    }});
  }}
  function openRemote() {{
    pywebview.api.open_remote(document.getElementById('url').value).then(function (result) {{
      if (!result.ok) document.getElementById('error').textContent = result.error;
    }});
  }}
</script>
"""


class DesktopUnavailable(Exception):
    """The window toolkit is not installed."""


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


def start_server() -> None:
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
    subprocess.Popen(server_command(), **options)  # noqa: S603 -- our own program


def ensure_running(settings: Settings) -> instance.ServerInfo | None:
    """The server for this data folder, started first if it is not running yet."""
    running = instance.find_running(settings.data_dir)
    if running is not None:
        return running
    start_server()
    return instance.wait_for(settings.data_dir, START_TIMEOUT_SECONDS)


def run_desktop(settings: Settings) -> None:
    try:
        import webview  # pyright: ignore[reportMissingImports]
    except ImportError as err:
        raise DesktopUnavailable(
            "The desktop window needs an extra package. Install it with: uv sync --extra desktop"
        ) from err

    log_path = settings.data_dir / "logs" / "server.log"

    class Api:
        def status(self) -> dict[str, object]:
            running = instance.find_running(settings.data_dir)
            return {"running": running is not None, "url": running.url if running else ""}

        def open_local(self) -> dict[str, object]:
            assert window is not None
            running = ensure_running(settings)
            if running is None:
                return {
                    "ok": False,
                    "error": f"Katib did not start. What went wrong is in {log_path}.",
                }
            window.load_url(running.url)
            return {"ok": True}

        def stop_local(self) -> dict[str, object]:
            running = instance.find_running(settings.data_dir)
            if running is None or instance.stop(running, settings.data_dir):
                return {"ok": True}
            return {"ok": False, "error": "Katib did not stop. It may still be finishing a job."}

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
        html=LAUNCHER_HTML.format(remote=html.escape(read_remote_choice())),
        js_api=Api(),
        width=1400,
        height=900,
    )
    assert window is not None  # only None when a window already exists, which none does here
    # Nothing to shut down afterwards: the server is not this window's to stop.
    webview.start()
