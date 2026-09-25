"""Starts Katib in its own window. This is what the installers run."""

import multiprocessing

from katib.desktop.window import run_desktop
from katib.config import load_settings

if __name__ == "__main__":
    multiprocessing.freeze_support()
    run_desktop(load_settings())
