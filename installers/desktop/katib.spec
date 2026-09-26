# PyInstaller recipe, shared by every desktop installer.
# Build it through installers/build.py rather than calling PyInstaller by hand.
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

here = Path(SPECPATH)
root = here.parent.parent
src = root / "src" / "katib"

hidden = collect_submodules("katib") + collect_submodules("uvicorn") + collect_submodules("webview")
hidden += ["psycopg", "argon2", "yaml"]
if sys.platform.startswith("linux"):
    # The GTK web view reaches for these at run time. PyInstaller's own gi hook then brings along
    # the typelib files they need.
    hidden += ["gi", "gi.repository.Gtk", "gi.repository.WebKit2", "cairo"]

a = Analysis(
    [str(here / "entry.py")],
    pathex=[str(root / "src")],
    datas=[
        (str(src / "static"), "katib/static"),
        (str(src / "db" / "migrations"), "katib/db/migrations"),
    ],
    hiddenimports=hidden,
    excludes=["tkinter", "onnxruntime", "onnx"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Katib",
    console=False,
    icon=str(here / ("icon.ico" if sys.platform == "win32" else "icon.png")),
)
coll = COLLECT(exe, a.binaries, a.datas, name="Katib")
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Katib.app",
        icon=str(here / "icon.icns"),
        bundle_identifier="app.katib.desktop",
    )
