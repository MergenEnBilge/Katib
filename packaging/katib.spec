# PyInstaller recipe. Build with: uv run --group packaging pyinstaller packaging/katib.spec
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).parent
src = root / "src" / "katib"

hidden = collect_submodules("katib") + collect_submodules("uvicorn") + collect_submodules("webview")
hidden += ["psycopg", "argon2", "yaml"]

a = Analysis(
    [str(root / "packaging" / "entry.py")],
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
    icon=str(root / "packaging" / ("icon.ico" if sys.platform == "win32" else "icon.png")),
)
coll = COLLECT(exe, a.binaries, a.datas, name="Katib")
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Katib.app",
        icon=str(root / "packaging" / "icon.icns"),
        bundle_identifier="app.katib.desktop",
    )
