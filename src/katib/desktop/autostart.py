"""Start Katib's server when you sign in to this computer, if you asked for that.

Each platform's own per-user mechanism, so none of it needs an administrator: a value under the
Run key on Windows, a LaunchAgent on macOS, and an XDG autostart entry on Linux. Off unless
someone turns it on from the tray.
"""

from __future__ import annotations

import os
import plistlib
import shlex
import subprocess
import sys
from pathlib import Path

NAME = "Katib Server"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
LAUNCH_AGENT_ID = "io.github.mergenenbilge.katib.server"


def server_command() -> list[str]:
    """What starts the background server without anyone asking just now (the window, sign-in):
    the installed program, or this Python when developing. Quiet, because nobody is watching
    for a message box; problems still go to the log."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        name = "KatibServer.exe" if os.name == "nt" else "KatibServer"
        return [str(exe.with_name(name)), "--quiet"]
    return [sys.executable, "-m", "katib", "tray-server", "--quiet"]


def _launch_agent() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_ID}.plist"


def _xdg_entry() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / "katib-server.desktop"


def is_enabled() -> bool:
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.QueryValueEx(key, NAME)
        except OSError:
            return False
        return True
    if sys.platform == "darwin":
        return _launch_agent().is_file()
    return _xdg_entry().is_file()


def enable() -> None:
    command = server_command()
    if sys.platform == "win32":
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(command))
    elif sys.platform == "darwin":
        path = _launch_agent()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            plistlib.dumps(
                {"Label": LAUNCH_AGENT_ID, "ProgramArguments": command, "RunAtLoad": True}
            )
        )
    else:
        path = _xdg_entry()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={NAME}\n"
            "Comment=Keeps Katib running for your other devices\n"
            f"Exec={shlex.join(command)}\n"
            "Icon=katib\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )


def disable() -> None:
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, NAME)
        except OSError:
            pass
    elif sys.platform == "darwin":
        _launch_agent().unlink(missing_ok=True)
    else:
        _xdg_entry().unlink(missing_ok=True)


def set_enabled(on: bool) -> None:
    if on:
        enable()
    else:
        disable()
