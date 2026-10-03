"""Starts Katib in its own window. This is what the installers run."""

import multiprocessing
import os
import sys

if __name__ == "__main__":
    # Started from Explorer, a program without a console has no standard streams at all, and
    # anything that writes to them fails. Give it somewhere harmless to write.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")  # noqa: SIM115
    multiprocessing.freeze_support()

    from katib.config import load_settings
    from katib.desktop.window import run_desktop

    run_desktop(load_settings())
