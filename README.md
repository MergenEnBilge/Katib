# Katib

**Label images with your team, on your own machine.**

Katib is an annotation tool for computer vision. You draw boxes and polygons on your images, organize them into classes, and export the result in the format your training code expects. It runs on your laptop with one command, or on a server your whole team shares. Your images never leave your hardware, and nothing is sent anywhere unless you set it up.

Most annotation tools are either a quick desktop app that falls apart once a second person joins, or a hosted service that wants your data. Katib is meant to be both easy to start and solid when the project grows to thousands of images and several people.

## Install

| You want | Do this |
|----------|---------|
| Katib on your own computer | Download the installer for your system from the [releases page](https://github.com/MergenEnBilge/Katib/releases) and open it. Windows gets a setup program, macOS a disk image, Linux a `.deb` or an archive |
| Katib for your team | One line with Docker, below |
| Katib on your Android phone | `Katib-android.apk` from the same releases page |
| Katib on your iPhone | Open your server in Safari and choose **Add to Home Screen**. See [installers/mobile](installers/mobile/README.md) |
| To work on Katib itself | From the source, below |

**With Docker.** This is the whole install:

```bash
docker run -d --name katib --restart unless-stopped -p 8420:8420 -v katib-data:/data ghcr.io/mergenenbilge/katib:latest
```

Open <http://localhost:8420>. On a Linux server, `curl -fsSL https://raw.githubusercontent.com/MergenEnBilge/Katib/main/install.sh | sh` does the same and prints the address for you. The [guide to putting Katib online](docs/deploy.md) has step-by-step help for Docker Desktop, servers and Raspberry Pi.

**From the source.** You need Python 3.12 or newer and Node 20 or newer. Install the two helper tools once:

```bash
pip install uv
npm install -g pnpm
```

Then, from this folder:

```bash
uv sync
pnpm --dir web install
pnpm --dir web build
uv run katib
```

Your browser opens on Katib. Nothing else is needed: the data lives in a small local database in your user folder.

If your terminal says `uv` is not recognized, `pip` put it in a folder that is not on your PATH. Put `python -m` in front of it instead, for example `python -m uv run katib`. If you are inside an activated virtual environment (your prompt starts with the environment name), `uv` is not installed in it, so run the `katib` command directly instead.

New to labeling? On the home page choose **Try it with practice pictures**. It makes a small project and walks you through it.

**Build the installers yourself.** One command, on the machine you want an installer for:

```bash
uv run python installers/build.py
```

The result lands in `dist/installers`. See [installers/README.md](installers/README.md) for what each platform needs.

## What you can do with it

- **Draw fast.** Boxes, polygons, rotated boxes, keypoints, brush masks, whole-image tags and text on a smooth canvas. Number keys pick classes, arrow keys nudge shapes, and every edit saves on its own. Undo and redo work as you expect.
- **Fix mistakes in bulk.** Rename a class and every shape follows. Merge two classes, delete one with all its shapes, or relabel a selection from the class gallery. Every bulk change shows what it will touch first, and you can undo it for 30 days, even after closing the browser.
- **Spot problems before you train.** The health panel finds tiny stray shapes, duplicates, near-identical photos, and classes with far fewer examples than the rest.
- **Bring your data, take it with you.** Import and export YOLO (detection, segmentation and rotated boxes), COCO (including keypoints), Pascal VOC and LabelMe, with train, validation and test splits. Importing the same file twice never doubles your labels.
- **Keep your splits.** Katib reads the train, validation and test split your dataset already has, keeps it on each image, and lets you reshuffle or set your own ratios for each kind of dataset. Exports use it.
- **Write about pictures.** Add captions to whole images and write the text found inside a shape, then export it as JSON Lines that loads straight into Hugging Face.
- **Learn as you go.** A practice project with a guided tour and a checklist gets a new person drawing in two minutes.
- **Work together.** Invite people with a link and give them a role: owner, manager, annotator, reviewer or viewer. Katib hands each annotator the next image, shows who else is on the project, and keeps two people from editing the same image at once. Reviewers can approve images or send them back with a comment.
- **Change everything in the app.** Every setting has a page in Settings with a plain explanation, and a backup is one button.
- **Learn with it, not from a manual.** Short tips appear the first time you use a tool or window, and tours explain the workspace, the home screen and Settings based on what your project has.
- **Set the window up your way.** Fold the sidebar, the image list or the details panel away with a button or a key, or give the picture the whole window with one press. Katib remembers how you left it.
- **Use any device.** The interface adapts from a wide desktop screen to a phone. Install it on a phone and it keeps working when the signal drops.

## Using Katib

### Your first project

1. Choose **New project** and give it a name.
2. Choose **Import images**. You can upload files from your computer, or connect a folder (see [Using a folder of images](#using-a-folder-of-images)).
3. In the **Classes** tab on the right, add a class such as `car`.
4. Press **B** for the box tool, drag on the image, and release. Press **P** for polygons: click to add points, then press **Enter** or click the first point to close the shape.
5. Press **Shift+Enter** to mark the image as done and move to the next one.
6. When you are ready, choose **Export**, pick a format, and download a zip file.

Press **?** at any time to see every shortcut.

### Choosing what to draw

When you create a project, pick the kinds of shapes it will use. You can only save the kinds you pick, and only those tools appear in the toolbar.

| Kind | Tool | How |
|------|------|-----|
| Boxes | **B** | Drag a rectangle. |
| Polygons | **P** | Click around an outline, then press Enter. |
| Rotated boxes | **O** | Drag along one edge, then move out to the other side and click. Drag the round handle to turn it. |
| Keypoints | **K** | Click each landmark in order. Shift+click marks one as hidden, N skips one, Enter finishes early. |
| Brush masks | **R** | Paint. E switches to the eraser, and [ and ] change the brush size. |
| Magic wand | **W** | Click inside an object and Katib outlines the area of similar color as a polygon. [ and ] change how alike the colors must be. |
| Image tags | | Switch a class on under "Tags on this image". |

Keypoints need landmarks. Open **Manage classes**, choose a class, and write its landmarks one per line, for example `nose`, `left eye`, `right eye`. To draw lines between them, write pairs of numbers such as `1-2, 1-3`.

### Pre-labeling with your own model

If you already have a YOLO detection model saved as ONNX, Katib can draft boxes for you to correct. Nothing is downloaded and nothing leaves your computer.

1. Install the extra package: `uv sync --extra ml`
2. Turn it on in `katib.toml`:

   ```toml
   [ml]
   enabled = true
   ```

3. Copy your `.onnx` file into the `models` folder inside Katib's data folder. The pre-label window shows the exact path.
4. In a project, choose **Pre-label with a model** (the sparkle button), pick the model and a minimum confidence, and run it.

Drafted boxes are drawn dashed and carry the model's confidence. Correct them like any other box. The whole run shows up in the history and can be undone for 30 days. Models exported from common YOLO tools list their own class names. If yours does not, the window asks you to type them in.

### Using a folder of images

Choose **Import images**, then **Connect a folder**. Katib shows the folders on your computer, starting from your home folder and drives. Click your way to the photos and press **Use this folder**. Katib reads the images where they are. It never copies, moves or changes your originals.

The folder stays connected to the project. When you add more photos to it later, open **Import images** and press the refresh button next to the folder. Only the new images are added. Disconnecting a folder keeps the images already in the project.

On a shared server, only the administrator can connect a new folder. Everyone else can import from folders that are already connected. You can also allow folders ahead of time in `katib.toml`:

```toml
[storage]
allowed_import_roots = ["/data/photos"]
```

### What each release contains

Each tagged version (for example `v0.1.0`) is built for Windows (`Katib-<version>-windows-setup.exe`), macOS (`Katib-<version>-macos.dmg`) and Linux (`katib_<version>_<arch>.deb` and `Katib-<version>-linux-<arch>.tar.gz`), along with `Katib-android.apk` and a Docker image for Intel and ARM machines. They are attached to the GitHub release. Install, open Katib, and it runs in its own window with its data in your user folder. The installers are not code-signed yet, so Windows and macOS may warn the first time you open one. On macOS, right-click the app and choose Open.

The `.deb` needs WebKitGTK (`gir1.2-webkit2-4.1`), which the package asks apt to install.

### Katib in its own window

If you would rather not use a browser tab, Katib can open in its own window:

```bash
uv sync --extra desktop
uv run katib app
```

The window runs Katib on your computer only, on a port nobody else can reach. Closing the window stops it.

## Working with a team

Turn on accounts, and Katib asks people to sign in. Add this to `katib.toml`:

```toml
[auth]
mode = "local"
```

Then start Katib so other computers on your network can reach it:

```bash
uv run katib share
```

That turns accounts on, listens on your network and prints the address to open, with a QR code you can scan with a phone. You can see the same address and code inside Katib: click your name at the bottom of the sidebar. Everyone must be on the same network. The address uses plain HTTP, so use it on a network you trust, or put HTTPS in front with the Docker setup below.

If you prefer to set it up yourself, use `uv run katib serve --host 0.0.0.0` with `mode = "local"` as above.

The first person to open the page creates the administrator account. From there, open a project, choose **Team**, and create an invite link for each person. A link works once and expires after seven days. The same window has a list of other Katib servers you use, so you can jump between a colleague's server and your own.

If you run Katib without accounts (`mode = "none"`), it only listens on your own computer, and it will refuse to start on a network address. This keeps an open instance from being exposed by accident.

### Running it on a server with Docker

This is the easiest way to run Katib for a team. It starts Katib, a Postgres database, and Caddy, which adds HTTPS.

```bash
cp .env.example .env
```

Open `.env` and set `KATIB_DB_PASSWORD`. Point `KATIB_PHOTOS` at the folder with your photos, and set `KATIB_HOST` to the name people will type, such as `katib.example.com` or the server's address. Then:

```bash
docker compose up -d
```

Open `https://` and that name. The first person to arrive creates the administrator account. In **Import images**, connect the folder called `/photos`.

On a public domain, set `KATIB_TLS` to your email address and Caddy gets a real certificate on its own. On a private network, leave it as `internal`. Caddy then signs its own certificate, and each browser shows a warning once. To remove the warning, install Caddy's root certificate on those computers. You can copy it from the running container:

```bash
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./katib-root.crt
```

Your data lives in Docker volumes, so it survives `docker compose down` and upgrades. To upgrade, pull the new code and run `docker compose up -d --build`.

### Using Postgres without Docker

Prefer Postgres to the built-in database? Install the driver and add the address to `katib.toml`:

```bash
uv sync --extra postgres
```

```toml
[database]
url = "postgresql://katib:secret@localhost/katib"
```

## On a phone or tablet

Open the address from **Share** on your phone. The interface fits the screen and you draw with a finger or a stylus.

On Android there is an app, `Katib-android.apk` on the releases page. It connects to your server and opens it full screen. On an iPhone, open your server in Safari and choose **Add to Home Screen** from the share sheet, which does the same thing without an app to install. Either way, see [installers/mobile](installers/mobile/README.md). Adding to the home screen needs a secure address, so use the Docker setup with HTTPS or open Katib on the same computer.

Once installed, Katib opens without a connection and keeps the images you have looked at. If the connection drops while you draw, your edits are kept on the device and sent the next time you open Katib with a connection. Images you have not opened yet are not available offline.

## Roles

| Role | What they can do |
|------|------------------|
| Owner | Everything, including deleting the project and managing members |
| Manager | Import, manage classes, assign images, review, export |
| Reviewer | Annotate, approve or send back finished images, comment |
| Annotator | Annotate and mark images done |
| Viewer | Look, but not change anything |

## Settings

Katib runs without any settings. Everything you might want to change is in **Settings** in the sidebar, each with a short explanation: who can use Katib, the port, where data lives, the folders Katib may read, limits, and model help. A setting either applies at once or tells you it needs a restart, and a **Restart Katib now** button does it for you. **Settings**, then **Backup**, makes a zip of your projects and uploads. Restore it with `katib restore your-backup.zip`.

If you prefer files, create `katib.toml` in the folder you start Katib from, or set an environment variable such as `KATIB_SERVER__PORT=9000`. Environment variables win, then settings saved in the app, then the file. See [Running a server](docs/server.md#settings) for the full list.

## Your data and your privacy

- Katib makes no network requests on its own. There is no telemetry.
- Passwords are stored with argon2id. Session and invite tokens are stored only as hashes.
- Your original images are only ever read.

## Your logo

The logo shown in Katib and used for every app icon comes from two files in `brand/`. Replace `logo.svg` and `logo.png` with yours and run `python scripts/apply_brand.py`. See `brand/README.md`. The ones there now are placeholders.

## Documentation

The full guide is in the `docs` folder: drawing and shortcuts, formats, teams, running a server, the API and security. To read it as a website, run `uv run --group docs mkdocs serve`.

## For developers

The backend is Python with FastAPI and SQLAlchemy. The frontend is Svelte 5 with TypeScript, and the drawing canvas is a small engine that does not depend on Svelte. `ARCHITECTURE.md` explains how the pieces fit together and `DESIGN.md` describes the interface.

Run the app with live reload:

```bash
uv run katib dev              # backend on :8420, reloads on change
pnpm --dir web dev            # frontend on :5173, proxies /api to the backend
```

Run the checks:

```bash
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run lint-imports
uv run pytest
pnpm --dir web check && pnpm --dir web lint && pnpm --dir web test
```

Browser tests drive the real app at desktop and phone sizes:

```bash
pnpm --dir web build
pnpm --dir web exec playwright install chromium
pnpm --dir web exec playwright test
```

To run the Python tests against Postgres, point `KATIB_TEST_POSTGRES_URL` at a server and add `--db postgres`. Each test gets its own schema and cleans up after itself.

After changing an API route, refresh the TypeScript types with `pnpm --dir web gen:api`.

## Status

Katib is under active development and has not had a stable release yet. Everything described above works today: labeling with six kinds of shapes and text, splits, class tools, dataset health, five dataset formats, teams with accounts, roles and review, sharing on a network, Docker with HTTPS, installing on a phone with offline edits, a desktop window, model pre-labeling, in-app settings and backups, and a Python client.

The Windows app has been run on Windows. The macOS and Linux installers and the published Docker image are built by the release workflow and have not yet been run on those systems.

Not available yet:

- Click-to-segment with a neural network. The magic wand covers simple cases.
- Translations. The interface is English, and the groundwork for other languages and right-to-left layouts is in place. See `docs/contributing.md`.

## License

MIT. See `LICENSE`.
