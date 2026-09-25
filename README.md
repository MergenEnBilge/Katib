# Katib

**Label images with your team, on your own machine.**

Katib is an annotation tool for computer vision. You draw boxes and polygons on your images, organize them into classes, and export the result in the format your training code expects. It runs on your laptop with one command, or on a server your whole team shares. Your images never leave your hardware, and nothing is sent anywhere unless you set it up.

Most annotation tools are either a quick desktop app that falls apart once a second person joins, or a hosted service that wants your data. Katib is meant to be both easy to start and solid when the project grows to thousands of images and several people.

## What you can do with it

- **Draw fast.** Boxes, polygons, rotated boxes, keypoints, brush masks and whole-image tags on a smooth canvas. Number keys pick classes, arrow keys nudge shapes, and every edit saves on its own. Undo and redo work as you expect.
- **Fix mistakes in bulk.** Rename a class and every shape follows. Merge two classes, delete one with all its shapes, or relabel a selection from the class gallery. Every bulk change shows what it will touch first, and you can undo it for 30 days, even after closing the browser.
- **Spot problems before you train.** The health panel finds tiny stray shapes, duplicates, near-identical photos, and classes with far fewer examples than the rest.
- **Bring your data, take it with you.** Import and export YOLO (detection, segmentation and rotated boxes), COCO (including keypoints), Pascal VOC and LabelMe, with train, validation and test splits. Importing the same file twice never doubles your labels.
- **Work together.** Invite people with a link and give them a role: owner, manager, annotator, reviewer or viewer. Katib hands each annotator the next image, shows who else is on the project, and keeps two people from editing the same image at once. Reviewers can approve images or send them back with a comment.
- **Use any device.** The interface adapts from a wide desktop screen to a phone. Install it on a phone and it keeps working when the signal drops.

## Get started in five minutes

You need Python 3.12 or newer and Node 20 or newer. Install the two helper tools once:

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

Katib can also be installed like an app. On Android, open the browser menu and choose **Install app**. On an iPhone, choose **Add to Home Screen** from the share sheet. This needs a secure address, so use the Docker setup with HTTPS or open Katib on the same computer.

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

Katib runs without any settings. To change something, create `katib.toml` in the folder you start Katib from, or set an environment variable such as `KATIB_SERVER__PORT=9000`.

| Setting | Default | What it does |
|---------|---------|--------------|
| `server.host` | `127.0.0.1` | Address to listen on |
| `server.port` | `8420` | Port to listen on |
| `auth.mode` | `none` | `none` for one person on one computer, `local` for accounts |
| `database.url` | SQLite in your data folder | Where projects are stored |
| `storage.data_dir` | Your user data folder | Where Katib keeps its database, thumbnails and uploads |
| `storage.allowed_import_roots` | none | Folders that everyone on a shared server may import from |
| `limits.max_upload_mb` | `50` | Largest file the browser may upload |
| `limits.operation_retention_days` | `30` | How long bulk changes stay undoable |

## Your data and your privacy

- Katib makes no network requests on its own. There is no telemetry.
- Passwords are stored with argon2id. Session and invite tokens are stored only as hashes.
- Your original images are only ever read.

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

Katib is under active development and has not had a stable release yet. Single-user labeling, class tools, dataset health, and team workflows with accounts, roles, review and live presence all work today. Docker packaging is done. Ready-made installers for Windows, macOS and Linux are not available yet.

## License

MIT. See `LICENSE`.
