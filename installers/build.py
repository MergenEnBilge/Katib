"""Build the Katib installer for the machine you are on.

    uv run --extra desktop --group packaging python installers/build.py

It builds the web interface, freezes the app with PyInstaller, then wraps the result the way the
platform expects: a setup program on Windows, a disk image on macOS, a .deb and a tar archive on
Linux. Everything it produces lands in dist/installers.

The extra and the group in that command bring in the window toolkit and PyInstaller, which a plain
`uv sync` leaves out.

Options:
    --version 1.2.3   stamp this version instead of the one in pyproject.toml
    --skip-web        reuse the interface already built into src/katib/static
"""

import argparse
import importlib.util
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "installers"
VERSION_PATTERN = r"\d+\.\d+\.\d+(?:[-+.][0-9A-Za-z.-]+)?"
SETUP = "uv run --extra desktop --group packaging python installers/build.py"


class Failed(Exception):
    """A step failed. Reported as one line rather than a traceback."""


def run(command: list[str]) -> None:
    print("->", " ".join(command), flush=True)
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        raise Failed(f"{Path(command[0]).name} failed with exit code {result.returncode}.")


def tool(name: str, advice: str) -> str:
    found = shutil.which(name)
    if not found:
        raise Failed(f"{name} is not installed. {advice}")
    return found


def installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:
        return False


def version_from_pyproject() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def build_web() -> None:
    pnpm = tool("pnpm", "Install Node 20 or newer, then run: npm install -g pnpm")
    run([pnpm, "--dir", "web", "install", "--frozen-lockfile"])
    run([pnpm, "--dir", "web", "build"])


def freeze() -> None:
    if not (ROOT / "src" / "katib" / "static" / "index.html").is_file():
        raise Failed("The web interface has not been built. Run this without --skip-web.")
    # Without pywebview the app freezes cleanly and then cannot open its window, so check for it
    # here rather than shipping something that fails on the person who installs it.
    missing = [name for name in ("PyInstaller", "webview") if not installed(name)]
    if missing:
        raise Failed(f"This environment is missing {' and '.join(missing)}. Build with:\n  {SETUP}")
    spec = ROOT / "installers" / "desktop" / "katib.spec"
    run([sys.executable, "-m", "PyInstaller", str(spec), "--noconfirm"])


def package_windows(version: str) -> None:
    iscc = shutil.which("iscc") or shutil.which("ISCC")
    if not iscc:
        raise Failed(
            "Inno Setup is not installed, so there is no setup program to build.\n"
            "Get it from https://jrsoftware.org/isdl.php. dist/Katib already works as a\n"
            "portable folder: run Katib.exe inside it."
        )
    run([iscc, f"/DVersion={version}", str(ROOT / "installers" / "windows" / "katib.iss")])


def package_macos(version: str) -> None:
    run(["sh", str(ROOT / "installers" / "macos" / "make-dmg.sh"), version])


def package_linux(version: str) -> None:
    if shutil.which("dpkg-deb"):
        run(["sh", str(ROOT / "installers" / "linux" / "make-deb.sh"), version])
    else:
        print("dpkg-deb is missing, so no .deb was built. The tar archive below still works.")
    name = f"Katib-{version}-linux-{platform.machine()}.tar.gz"
    run(["tar", "-C", "dist", "-czf", f"dist/installers/{name}", "Katib"])


PACKAGERS = {"Windows": package_windows, "Darwin": package_macos, "Linux": package_linux}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--version", default=None, help="the version to stamp on the installer")
    parser.add_argument("--skip-web", action="store_true", help="reuse the built interface")
    args = parser.parse_args()

    system = platform.system()
    package = PACKAGERS.get(system)
    if package is None:
        raise Failed(f"There is no installer recipe for {system} yet.")

    version = args.version or version_from_pyproject()
    if not re.fullmatch(VERSION_PATTERN, version):
        raise Failed(f"{version!r} does not look like a version, for example 1.2.3")

    if not args.skip_web:
        build_web()
    freeze()

    OUT.mkdir(parents=True, exist_ok=True)
    package(version)

    made = sorted(p.name for p in OUT.iterdir() if p.is_file())
    if not made:
        print("Nothing was written to dist/installers.", file=sys.stderr)
        return 1
    print("\nIn dist/installers:")
    for filename in made:
        print("  ", filename)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Failed as problem:
        print(f"\n{problem}", file=sys.stderr)
        raise SystemExit(1) from None
