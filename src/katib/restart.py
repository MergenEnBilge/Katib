"""Start Katib again from inside itself, so a setting that needs a restart can be applied."""

import os
import subprocess
import sys
import threading

DELAY_SECONDS = 0.7


def command() -> list[str]:
    """The command that started this process. A packaged app has no script name to repeat."""
    if getattr(sys, "frozen", False):
        return [sys.executable, *sys.argv[1:]]
    return [sys.executable, *sys.argv]


def restart_now() -> None:
    args = command()
    if os.name == "nt":
        # Windows cannot replace a running program, so start a second copy and leave.
        subprocess.Popen(args, close_fds=True)  # noqa: S603
        os._exit(0)
    os.execv(args[0], args)  # noqa: S606


def restart_soon() -> None:
    """Restart after the reply has gone out."""
    threading.Timer(DELAY_SECONDS, restart_now).start()
