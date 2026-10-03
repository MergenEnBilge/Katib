"""Telling someone something went wrong when there is no console and no window to say it in,
and opening a file such as the log in whatever this computer uses to read it.

Each platform's own means, and best effort only: if none is available the message still went to
the log, and Katib carries on rather than failing a second time over how it reports the first.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def show_error(title: str, message: str) -> None:
    """A message box with an OK button. Blocks until it is dismissed."""
    try:
        if sys.platform == "win32":
            import ctypes

            mb_iconerror, mb_topmost = 0x10, 0x40000
            ctypes.windll.user32.MessageBoxW(None, message, title, mb_iconerror | mb_topmost)
        elif sys.platform == "darwin":
            script = (
                f"display alert {_applescript(title)} message {_applescript(message)} as critical"
            )
            subprocess.run(["osascript", "-e", script], check=False, timeout=600)  # noqa: S607
        else:
            for tool in (
                ["zenity", "--error", f"--title={title}", f"--text={message}"],
                ["kdialog", "--title", title, "--error", message],
                ["notify-send", "--urgency=critical", title, message],
            ):
                if shutil.which(tool[0]):
                    subprocess.run(tool, check=False, timeout=600)  # noqa: S603
                    break
    except Exception:  # noqa: BLE001 -- reporting a problem must never become a second one
        log.warning("Could not show the message %r on screen.", title, exc_info=True)


def open_path(path: Path) -> bool:
    """Open a file or folder the way double-clicking it would. False if that is not possible."""
    if not path.exists():
        return False
    try:
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606 -- a path Katib chose, opened for its owner
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])  # noqa: S603, S607
        else:
            subprocess.Popen(["xdg-open", str(path)])  # noqa: S603, S607
    except OSError:
        log.warning("Could not open %s.", path, exc_info=True)
        return False
    return True


def _applescript(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
