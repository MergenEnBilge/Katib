# PyInstaller recipe, shared by every desktop installer.
# Build it through installers/build.py rather than calling PyInstaller by hand.
#
# Two programs share one folder: Katib, the window, and KatibServer, the background server with
# its tray icon. The window starts the server when none is running; the server outlives the window.
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

here = Path(SPECPATH)
root = here.parent.parent
src = root / "src" / "katib"

hidden = collect_submodules("katib") + collect_submodules("uvicorn") + collect_submodules("webview")
hidden += collect_submodules("pystray")
hidden += ["psycopg", "argon2", "yaml", "PIL.Image", "PIL.ImageDraw"]
if sys.platform.startswith("linux"):
    # The GTK web view reaches for these at run time. PyInstaller's own gi hook then brings along
    # the typelib files they need.
    hidden += ["gi", "gi.repository.Gtk", "gi.repository.WebKit2", "cairo"]

common = dict(
    pathex=[str(root / "src")],
    datas=[
        (str(src / "static"), "katib/static"),
        (str(src / "db" / "migrations"), "katib/db/migrations"),
    ],
    hiddenimports=hidden,
    excludes=["tkinter", "onnxruntime", "onnx"],
)
icon = str(here / ("icon.ico" if sys.platform == "win32" else "icon.png"))

window = Analysis([str(here / "entry.py")], **common)
server = Analysis([str(here / "server_entry.py")], **common)

window_exe = EXE(
    PYZ(window.pure),
    window.scripts,
    [],
    exclude_binaries=True,
    name="Katib",
    console=False,
    icon=icon,
)
server_exe = EXE(
    PYZ(server.pure),
    server.scripts,
    [],
    exclude_binaries=True,
    name="KatibServer",
    console=False,
    icon=icon,
)
coll = COLLECT(
    window_exe,
    server_exe,
    window.binaries,
    window.datas,
    server.binaries,
    server.datas,
    name="Katib",
)
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Katib.app",
        icon=str(here / "icon.icns"),
        bundle_identifier="app.katib.desktop",
    )
