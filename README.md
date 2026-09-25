# Katib

**Label images with your team, on your own machine.**

Katib is an annotation tool for computer vision. You draw boxes and polygons on your images, organize them into classes, and export the result in the format your training code expects. It runs on your laptop with one command, or on a server your whole team shares. Your images never leave your hardware, and nothing is sent anywhere unless you set it up.

Most annotation tools are either a quick desktop app that falls apart once a second person joins, or a hosted service that wants your data. Katib is meant to be both easy to start and solid when the project grows to thousands of images and several people.

## What you can do with it

- **Draw fast.** Boxes and polygons on a smooth canvas. Number keys pick classes, arrow keys nudge shapes, and every edit saves on its own. Undo and redo work as you expect.
- **Fix mistakes in bulk.** Rename a class and every shape follows. Merge two classes, delete one with all its shapes, or relabel a selection from the class gallery. Every bulk change shows what it will touch first, and you can undo it for 30 days, even after closing the browser.
- **Spot problems before you train.** The health panel finds tiny stray shapes, duplicates, near-identical photos, and classes with far fewer examples than the rest.
- **Bring your data, take it with you.** Import and export YOLO and COCO, including train, validation and test splits. Importing the same file twice never doubles your labels.
- **Work together.** Invite people with a link and give them a role: owner, manager, annotator, reviewer or viewer. Katib hands each annotator the next image, shows who else is on the project, and keeps two people from editing the same image at once. Reviewers can approve images or send them back with a comment.
- **Use any device.** The interface adapts from a wide desktop screen to a phone.

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
2. Choose **Import images**. You can upload files from your computer, or point Katib at a folder (see [Using a folder of images](#using-a-folder-of-images)).
3. In the **Classes** tab on the right, add a class such as `car`.
4. Press **B** for the box tool, drag on the image, and release. Press **P** for polygons: click to add points, then press **Enter** or click the first point to close the shape.
5. Press **Shift+Enter** to mark the image as done and move to the next one.
6. When you are ready, choose **Export**, pick a format, and download a zip file.

Press **?** at any time to see every shortcut.

### Using a folder of images

Katib reads images where they are. It never copies, moves or changes your originals. For safety, it only reads folders you allow. Create a file named `katib.toml` next to this README:

```toml
[storage]
allowed_import_roots = ["/data/photos"]
```

On Windows, use forward slashes, for example `"C:/Users/you/Pictures"`. Restart Katib, then paste that folder path into **Import images**.

## Working with a team

Turn on accounts, and Katib asks people to sign in. Add this to `katib.toml`:

```toml
[auth]
mode = "local"
```

Then start Katib so other computers on your network can reach it:

```bash
uv run katib serve --host 0.0.0.0
```

The first person to open the page creates the administrator account. From there, open a project, choose **Team**, and create an invite link for each person. A link works once and expires after seven days.

If you run Katib without accounts (`mode = "none"`), it only listens on your own computer, and it will refuse to start on a network address. This keeps an open instance from being exposed by accident.

Prefer Postgres to the built-in database? Install the driver and add the address to `katib.toml`:

```bash
uv sync --extra postgres
```

```toml
[database]
url = "postgresql://katib:secret@localhost/katib"
```

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
| `storage.allowed_import_roots` | none | Folders Katib may read images from |
| `limits.max_upload_mb` | `50` | Largest file the browser may upload |
| `limits.operation_retention_days` | `30` | How long bulk changes stay undoable |

## Your data and your privacy

- Katib makes no network requests on its own. There is no telemetry.
- Passwords are stored with argon2id. Session and invite tokens are stored only as hashes.
- Your original images are only ever read.

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

Katib is under active development and has not had a stable release yet. Single-user labeling, class tools, dataset health, and team workflows with accounts, roles, review and live presence all work today. Docker packaging, a desktop app, and offline support for phones are next.

## License

MIT. See `LICENSE`.
