"""Starts Katib's background server with its tray icon. The Katib window runs this when no
server is running yet, and so does signing in, once "Start when I sign in" is on.

`--stop` asks a running server to stop instead, which the uninstaller uses before removing files.
`--quiet` is how the window and sign-in start it: problems go to the log without message boxes.
"""

import multiprocessing
import os
import sys

if __name__ == "__main__":
    # Started from Explorer, a program without a console has no standard streams at all, and
    # anything that writes to them -- a logging handler, a library's banner -- fails. Give it
    # somewhere harmless to write; the real log goes to the data folder.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")  # noqa: SIM115
    multiprocessing.freeze_support()

    from katib.config import load_settings
    from katib.desktop.tray import run
    from katib.server import instance

    settings = load_settings()
    if "--stop" in sys.argv[1:]:
        running = instance.find_running(settings.data_dir)
        sys.exit(0 if running is None or instance.stop(running, settings.data_dir) else 1)
    sys.exit(run(settings, quiet="--quiet" in sys.argv[1:]))
