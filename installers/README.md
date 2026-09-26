# Installers

Everything that turns Katib into something people can install lives here.

| Folder | What it makes |
|--------|---------------|
| `desktop` | The frozen application: one folder that runs without Python installed. Shared by all three desktop installers |
| `windows` | `Katib-<version>-windows-setup.exe`, an Inno Setup installer |
| `macos` | `Katib-<version>-macos.dmg`, a disk image you drag into Applications |
| `linux` | `katib_<version>_<arch>.deb`, plus a tar archive for everything else |
| `mobile` | The Android APK and the iPhone app, both of which connect to a server you run |

## Building the desktop installer

One command, on the machine you want an installer for:

```bash
uv run python installers/build.py
```

It builds the web interface, freezes the app and wraps it for the platform you are on. The result
lands in `dist/installers`. Add `--skip-web` to reuse an interface you have already built.

You need:

| Platform | Also needed |
|----------|-------------|
| Windows | [Inno Setup](https://jrsoftware.org/isdl.php). Without it you still get `dist/Katib`, which runs as a portable folder |
| macOS | Nothing beyond Xcode's command line tools |
| Linux | `dpkg-deb` for the .deb, and `libgirepository1.0-dev libcairo2-dev gir1.2-webkit2-4.1 pkg-config` to build the window toolkit |

Cross-building is not possible: a Windows installer has to be built on Windows. That is what the
`release` workflow is for. It runs this same script on all three and attaches the results to the
release.

## Building the phone apps

See [mobile/README.md](mobile/README.md).

## Not here

- `install.sh` in the repository root installs Katib on a server with Docker in one command.
- `Dockerfile` and the compose files stay in the root, where Docker expects to find them.
