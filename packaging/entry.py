"""Starts Katib in its own window. This is what the installers run."""

import multiprocessing

from katib.config import load_settings
from katib.desktop.window import run_desktop

if __name__ == "__main__":
    multiprocessing.freeze_support()
    run_desktop(load_settings())
