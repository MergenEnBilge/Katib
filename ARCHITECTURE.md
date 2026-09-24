# Katib architecture

Katib is a data annotation tool. Images first (bounding boxes, polygons, oriented boxes, keypoints, masks, tags), with a design that leaves room for other data types later. It runs on a phone, on a PC you self-host, or as a desktop app, and all three can work on the same project at the same time.

This document is the technical source of truth. `DESIGN.md` covers the interface, `README.md` covers running and checking the code. If code and this document disagree, fix one of them in the same commit.

## Contents

1. [Principles](#1-principles)
2. [System overview](#2-system-overview)
3. [Deployment modes](#3-deployment-modes)
4. [Repository layout](#4-repository-layout)
5. [Layers and dependency rules](#5-layers-and-dependency-rules)
6. [Data model](#6-data-model)
7. [Annotation types](#7-annotation-types)
8. [Class operations](#8-class-operations)
9. [Collaboration](#9-collaboration)
10. [Undo and redo](#10-undo-and-redo)
11. [API](#11-api)
12. [Images and storage](#12-images-and-storage)
13. [Format plugins](#13-format-plugins)
14. [Background jobs](#14-background-jobs)
15. [Auth and security](#15-auth-and-security)
16. [Model assistance](#16-model-assistance)
17. [Frontend](#17-frontend)
18. [Configuration](#18-configuration)
19. [Performance targets](#19-performance-targets)
20. [Testing](#20-testing)
21. [Milestones](#21-milestones)
22. [Non-goals](#22-non-goals)
23. [Decisions log](#23-decisions-log)

---

## 1. Principles

1. **One server, thin clients.** Every device is a client of one Katib server. There is no sync engine between servers.
2. **Boring where possible.** A modular monolith, SQL, REST plus one WebSocket. New moving parts (queues, caches, extra services) need a written reason.
3. **Classes are rows, not strings.** Annotations point at a class by id. This is what makes rename, merge and delete-all instant and safe.
4. **Originals are read-only.** Katib never modifies or moves a user's image files.
5. **Nothing is lost silently.** Destructive operations show a preview, ask for confirmation when large, and can be undone.
6. **Local by default, shared on request.** `katib` on a laptop works with no account and no network.
7. **Simple beats configurable.** Add a setting only when two reasonable users would choose differently.

## 2. System overview

```
   Browser            Phone (PWA)          Desktop app
  (laptop / PC)     (installable web)   (server + native window)
        \                  |                   /
         \_________________|__________________/
                           |
                  REST + WebSocket (HTTPS when shared)
                           |
        +------------------v-------------------+
        |            Katib server (Python)     |
        |                                      |
        |   api        REST routes, WebSocket  |
        |   services   projects, classes,      |
        |              annotations, tasks      |
        |   formats    YOLO, COCO, VOC, ...    |
        |   jobs       import, export, thumbs  |
        |   ml         optional predictors     |
        |   core       pure geometry and types |
        +---------+-------------------+--------+
                  |                   |
         SQLite or Postgres     Image storage
                                (folder or S3)
```

The desktop app is the same server started on `127.0.0.1` with a native window pointing at it. A desktop app can also run in client mode against a remote server.

## 3. Deployment modes

| Mode | Command | Database | Auth | Notes |
|------|---------|----------|------|-------|
| Local | `katib` | SQLite | off | Binds to `127.0.0.1` only. Opens the browser. |
| LAN share | `katib serve --host 0.0.0.0` | SQLite or Postgres | on | Prints a URL and QR code. Phones join through the browser. |
| Server | `docker compose up` | Postgres | on | Katib, Postgres and Caddy (automatic HTTPS) in one compose file. |
| Desktop | installer | SQLite | off, or on when shared | Same server in a native window. Can toggle sharing on. |

Two rules follow from this table:

- Auth mode `none` refuses to start on any non-loopback address.
- Sharing a local instance switches auth on and creates the first admin account in a one-time setup screen.

**HTTPS on a LAN.** Browsers only allow service workers and PWA install in a secure context. `http://192.168.x.x` is not one. Annotating still works over plain HTTP, but offline support and install do not. The "Share on network" flow explains this and offers three routes: Caddy with a local certificate, Tailscale, or a tunnel.

**Moving data between instances** uses a `.katib` bundle (a zip with the project database export, class definitions, and optionally the images). There is no live sync between servers.

## 4. Repository layout

```
katib/
  pyproject.toml
  README.md
  ARCHITECTURE.md
  DESIGN.md
  src/katib/
    core/          Pure Python. Geometry, annotation types, validation. No I/O.
    db/            SQLAlchemy models, session handling, Alembic migrations.
    services/      Business logic: projects, classes, annotations, tasks, class ops.
    api/           FastAPI routers, request/response schemas, WebSocket hub.
    auth/          Password hashing, sessions, API tokens, permissions.
    storage/       Image storage backends (local folder now, S3 later).
    formats/       One module per format: yolo, coco, voc, labelme.
    jobs/          Job runner and job implementations.
    ml/            Optional predictors (extra: katib[ml]).
    desktop/       Native window launcher.
    config.py      Settings loading (toml + environment).
    cli.py         Typer entry point.
    static/        Built frontend (generated, not committed).
  web/             Svelte + TypeScript frontend.
  sdk/             katib-client, the Python SDK.
  docs/
    adr/           Architecture decision records.
    design/        Reference prototype (not shipped).
  docker/
  scripts/         bench.py, seed.py, release helpers.
  tests/
```

The built frontend is copied into `src/katib/static/` during the wheel build, so `pip install katib` includes the UI.

## 5. Layers and dependency rules

Imports flow one way:

```
api  ->  services  ->  db, storage, jobs
             |
             v
           core   <-  formats
```

- `core` imports nothing from the rest of Katib and does no I/O. It is the easiest layer to test and the one that changes least.
- `services` hold all business rules. Routes stay thin: parse, call a service, shape the response.
- `formats` depend only on `core` types. A format never touches the database. It reads and writes through a `DatasetView` (see section 13).
- `db` holds models and queries. No business rules.
- Nothing imports from `api` except `api` itself and the app entry point.

A linter check (`import-linter`) enforces these rules in CI.

**Sync vs async.** Services and routes are synchronous. FastAPI runs `def` routes in a thread pool, which is fast enough at this scale and keeps the code and tests simple. Async is used only where it matters: WebSocket handlers and streaming image responses. Decision recorded in ADR-001.

## 6. Data model

All primary keys are UUIDv7 (time-sortable). Annotation ids are generated on the client so a retried request is idempotent.

Timestamps are UTC. JSON columns use the database's native JSON type.

### users
`id`, `email` (unique), `name`, `password_hash`, `is_admin`, `created_at`, `disabled_at`

### projects
`id`, `name`, `slug`, `settings` (JSON), `created_by`, `created_at`, `archived_at`

`settings` holds: enabled annotation types, `review_enabled`, image import root, default export preset, per-project shortcut overrides.

### project_members
`project_id`, `user_id`, `role` (`owner`, `manager`, `annotator`, `reviewer`, `viewer`). Primary key is `(project_id, user_id)`.

### images
`id`, `project_id`, `filename`, `storage_key`, `width`, `height`, `sha256`, `phash`, `status`, `assignee_id`, `reviewer_id`, `locked_by`, `locked_until`, `position`, `version`, `created_at`, `updated_at`

- `status`: `todo`, `in_progress`, `done`, `approved`, `rejected`.
- `position` gives a stable order independent of filename.
- Unique on `(project_id, sha256)` is optional per project: importing a duplicate warns instead of failing.
- Indexes: `(project_id, status)`, `(project_id, position)`, `(project_id, assignee_id)`.

### classes
`id`, `project_id`, `name`, `color`, `position`, `attr_schema` (JSON), `created_at`

- Unique on `(project_id, lower(name))`.
- `position` is the export index order. Reordering is a first-class action.
- `attr_schema` is a list of `{name, type, options?}` where type is `boolean`, `enum`, `text` or `number`.

### class_aliases
`project_id`, `alias` (lowercased), `class_id`. Filled by rename and merge so that old names still resolve on import.

### annotations
`id`, `image_id`, `class_id`, `type`, `geometry` (JSON), `attrs` (JSON), `source` (`manual`, `model`, `import`), `confidence`, `created_by`, `created_at`, `updated_at`, `version`

- Indexes: `(image_id)`, `(class_id)`. The second one is what keeps class operations fast.
- `project_id` is deliberately not duplicated here. Join through `images` when needed, or add a denormalized column only if a benchmark shows it matters.

### comments
`id`, `image_id`, `annotation_id` (nullable), `x`, `y` (normalized, nullable), `author_id`, `body`, `resolved_at`, `created_at`

### operations
`id`, `project_id`, `user_id`, `kind`, `summary`, `inverse_ref`, `created_at`, `reverted_at`

Every destructive or bulk action (merge, delete class, bulk reclass, bulk delete, import) writes a row here. `inverse_ref` points at a compressed JSON file in the data directory holding what is needed to reverse the action. See section 8.

### activity
`id`, `project_id`, `user_id`, `verb`, `payload` (JSON), `created_at`. Feeds the "Recent activity" panel. Kept separate from `operations` because most activity is not reversible.

### jobs
`id`, `project_id`, `kind`, `status`, `progress`, `params`, `result`, `error`, `created_by`, `created_at`, `finished_at`

### api_tokens
`id`, `user_id`, `name`, `token_hash`, `created_at`, `last_used_at`, `revoked_at`

## 7. Annotation types

Geometry is stored **normalized** (0 to 1, origin top-left) so it does not depend on image resolution and maps directly onto YOLO. Pixel values appear only in the UI and in formats that require them.

| `type` | `geometry` | Notes |
|--------|------------|-------|
| `box` | `{x, y, w, h}` | Top-left corner plus size. |
| `polygon` | `{points: [[x, y], ...]}` | At least 3 points. Single ring. |
| `obb` | `{cx, cy, w, h, angle}` | Oriented box. Angle in radians. |
| `keypoints` | `{points: [{x, y, v}, ...]}` | `v` is 0 not labeled, 1 hidden, 2 visible. Skeleton lives in the class. |
| `mask` | `{rle: "...", size: [w, h]}` | Brush masks, stored as run-length encoding. Added in M5. |
| `tag` | `{}` | Image-level label. No geometry. |

New types register in `core/types.py` with three things: a Pydantic model for the geometry, a validator, and a bounds function (used for the class gallery crops and box-size filters). The API, formats and frontend tool registry each add their own handling. Nothing else needs to change.

## 8. Class operations

These are the features that set Katib apart, so their semantics are fixed here.

**Rename.** Update `classes.name`. Add the old name to `class_aliases`. Annotations are untouched.

**Recolor, reorder, edit attributes.** Update the class row only. Removing an attribute from a schema leaves stored values in place (they are ignored, and reappear if the attribute is re-added). Explicit cleanup is a separate action.

**Merge `source` into `target`.** In one transaction:
1. Collect the ids of annotations on `source` and their current `attrs` (only where attrs will change).
2. `UPDATE annotations SET class_id = target WHERE class_id = source`.
3. Drop attribute values that `target` does not define.
4. Add `source.name` to `class_aliases` pointing at `target`.
5. Delete the `source` class and close the gap in `position` values.
6. Write an `operations` row whose inverse file holds the source class row, the moved annotation ids, and the original attrs.

**Delete a class and all its annotations.** Same transaction shape. The inverse file holds the class row and every deleted annotation. Because this can be large, the file is compressed and stored under `data/operations/`.

**Bulk reclass and bulk delete** (from the class gallery or a filter) follow the same pattern.

**Preview before commit.** Every bulk action has a `dry_run` mode that returns counts (annotations affected, images affected, attribute values that would be dropped). The UI shows this before the user confirms.

**Reverting.** `POST /operations/{id}/revert` restores what it can. Annotations edited after the operation are skipped and counted in the response ("Restored 1,204 of 1,210. 6 were edited since."). Operations older than the retention window (default 30 days) have their inverse files deleted and cannot be reverted.

**Export order warning.** Each export records the class order it used. If the order has changed since the last export, the export dialog says so, because YOLO indices would no longer match older trained models.

## 9. Collaboration

The model is deliberately small. Two people are almost never on the same image, so the design prevents collisions instead of resolving them.

### Roles

| Role | Can do |
|------|--------|
| owner | Everything, including delete project and manage members |
| manager | Import, classes, assign, review, export |
| annotator | Annotate assigned or claimed images, mark done |
| reviewer | Approve or reject, comment, edit annotations |
| viewer | Read only |

In local mode the single implicit user is owner.

### Task flow

```
todo -> in_progress -> done -> approved
                        \-> rejected -> in_progress
```

- Without review (`review_enabled = false`), `done` is the end state.
- `POST /projects/{id}/next` picks the next `todo` image for the caller (or their existing `in_progress` one), sets the assignee, and returns it. In Postgres it uses `FOR UPDATE SKIP LOCKED`. In SQLite it runs inside a write transaction.
- A manager can also assign images or ranges to a specific person.
- "Done with zero annotations" is valid and means "no objects here".

### Soft locks

Opening an image for editing calls `POST /images/{id}/lock`. The lock lasts 45 seconds and the client renews it every 15. A second person opening the same image sees who holds it and gets read-only access, with a "Take over" action for managers. Locks are advisory. They prevent almost all conflicts, and versions catch the rest.

### Versions

Each annotation carries a `version`. Updates send `if_version`. A mismatch returns `409` with the current record, and the client shows a small "changed by Sam" prompt instead of overwriting.

### Save protocol

Clients do not send the whole image on save. They send batched operations:

```
POST /api/v1/images/{id}/annotations:batch
{ "ops": [
    {"op": "create", "id": "<uuid>", "type": "box", "class_id": "...", "geometry": {...}, "attrs": {}},
    {"op": "update", "id": "<uuid>", "if_version": 3, "patch": {"geometry": {...}}},
    {"op": "delete", "id": "<uuid>", "if_version": 2}
] }
```

Because ids come from the client and operations are idempotent, a request can be retried safely. This is what makes the offline outbox (section 17) work.

### Live events

One WebSocket per client at `/api/v1/ws?project=<id>`. Messages are small JSON events:

- `presence`: who is in the project and which image they are on
- `image.locked`, `image.unlocked`, `image.status`
- `annotation.changed`: sent to others viewing the same image
- `class.changed`: name, color, order or merge
- `job.progress`

Events are hints. Clients treat the REST API as the source of truth and refetch on reconnect.

### Multi-process

The WebSocket hub is in-process by default. If someone runs several workers, a Redis pub/sub adapter sits behind the same `Hub` interface. It is not built until needed.

## 10. Undo and redo

Two separate mechanisms, because they have different scopes.

**Shape edits (client).** Each open image has a command stack: `create`, `update`, `delete`, `reclass`. A command knows how to apply and how to reverse itself and emits the batch operations that go to the server. Undoing generates the inverse operations, so the server never needs to know undo exists. The stack is per image and per session, capped at 200 commands, and cleared when the image is closed.

**Bulk operations (server).** Class merges, deletes and other bulk actions use the `operations` table (section 8). They appear in a history panel and in the toast that follows the action. They survive reloads and work across users.

The prototype snapshots the whole project on every edit. Do not carry that over.

## 11. API

Base path `/api/v1`. JSON everywhere. FastAPI generates the OpenAPI spec, and the frontend types are generated from it (`openapi-typescript`) so the two sides cannot drift.

Conventions:

- **Resources:** `/projects`, `/projects/{id}/images`, `/projects/{id}/classes`, `/images/{id}/annotations`, `/operations`, `/jobs`, `/users`.
- **Actions** use a colon suffix: `/images/{id}/annotations:batch`, `/classes/{id}:merge`, `/projects/{id}:export`.
- **Pagination** is keyset-based: `?after=<id>&limit=100`. Responses include `next` when there is more. No offset pagination, because projects can have hundreds of thousands of images.
- **Filtering** uses query parameters: `status`, `assignee`, `class_id`, `q` (filename search), `has_annotations`.
- **Errors** share one shape: `{ "code": "class_name_taken", "message": "A class named \"car\" already exists.", "details": {} }`. Messages are written for humans and can be shown directly.
- **Auth:** an httpOnly, SameSite=Lax session cookie for the web app and `Authorization: Bearer` for tokens. Unsafe methods check the `Origin` header.
- **Versioning:** breaking changes go in `/api/v2`. Additive changes do not.

Image bytes:

- `GET /images/{id}/file` serves the original with `ETag` and range support.
- `GET /images/{id}/thumb?size=256` serves a cached thumbnail.

## 12. Images and storage

### Getting images in

Two import modes:

1. **Upload** (browser or phone). Files are stored under `data/uploads/<project>/`.
2. **Folder reference** (server side). An admin lists allowed roots in `storage.allowed_import_roots`. A manager picks a folder inside one of them, and Katib indexes the files where they are. Nothing is copied.

Both modes hash each file, read dimensions, generate a thumbnail and compute a perceptual hash as a background job. Formats: JPG, PNG, WebP, BMP, TIFF. EXIF orientation is applied at display and export time, never written back to the file.

### Storage interface

```python
class Storage(Protocol):
    def put(self, key: str, data: BinaryIO) -> None: ...
    def open(self, key: str) -> BinaryIO: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...
    def url(self, key: str) -> str | None: ...  # presigned URL if supported
```

`LocalStorage` ships in M1. `S3Storage` is added later without touching the rest of the code.

### Safety

- Folder imports resolve real paths and reject anything outside an allowed root (no `..`, no symlink escapes).
- Pillow's `MAX_IMAGE_PIXELS` is set explicitly, and uploads have a size limit.
- Filenames are stored as data. They are never used to build filesystem paths.
- Deleting a project never deletes referenced image files.

## 13. Format plugins

Each format is one module implementing:

```python
class Format(Protocol):
    id: str  # "yolo-detect", "coco", "voc"
    label: str
    supports: set[str]  # annotation types it can represent

    def detect(self, path: Path) -> bool: ...
    def read(self, path: Path, ctx: ImportContext) -> ImportReport: ...
    def write(self, data: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport: ...
```

`DatasetView` is a read-only, streaming view of images, annotations and classes in `core` types. A format never sees the database. Formats register through the `katib.formats` entry point so outside packages can add more.

Build order: YOLO detect, COCO (boxes and polygons), YOLO segment, Pascal VOC, LabelMe (import), YOLO OBB, COCO keypoints.

Export options:
- Which images (all, done only, approved only, a filter).
- Train/val/test split: ratios, seed, random or stratified by class.
- Classes to include, and the index order (with the warning from section 8).
- For YOLO: a generated `data.yaml`. For COCO: image ids and category ids kept stable across exports.

Import behaviour:
- Names resolve through `classes` and `class_aliases`. Unknown names are listed in a preview with "create" or "map to..." choices.
- Every import returns a report: files read, annotations created, skipped and why. Skipped items never vanish silently.
- Imports write an `operations` row, so a bad import can be reverted.
- Images are matched by filename, or by name without extension for YOLO. An image that already has shapes is skipped, so importing the same file twice cannot duplicate them. Reverting an import arrives with the operations log in M2.

Testing rule: every format has golden files and a round-trip test (import, export, compare).

## 14. Background jobs

A `jobs` table plus an in-process worker pool (threads for I/O, a process pool for CPU work such as thumbnails and model inference). Progress is written to the row and pushed over the WebSocket. Jobs survive restarts: on startup, jobs left `running` are marked `failed` with a clear message, and the user can retry.

Job kinds: `import_images`, `import_annotations`, `export`, `thumbnails`, `phash`, `prelabel`, `validate`.

Celery or RQ come in only if a deployment needs multiple worker machines. The job interface is small enough to swap.

## 15. Auth and security

- Passwords: argon2id. Login is rate-limited per account and per IP.
- Sessions: server-side session records, httpOnly cookies, rotation on login.
- API tokens: shown once, stored hashed, revocable.
- First admin: created in a setup screen that only works while no users exist.
- Invites: single-use links with an expiry. Registration is otherwise closed.
- Permissions are checked in services, not in routes, so the CLI and jobs get the same checks.
- Response headers: a strict CSP, `X-Content-Type-Options`, `Referrer-Policy`.
- No default credentials. No telemetry. Katib makes no outbound requests unless the user configures something (S3, model downloads).
- Later: OIDC login.

## 16. Model assistance

Optional and separate, installed with `pip install katib[ml]`.

```python
class Predictor(Protocol):
    id: str
    label: str
    kind: Literal["detect", "segment", "interactive"]

    def load(self, device: str) -> None: ...
    def predict(self, image: Image, prompt: Prompt | None) -> list[Prediction]: ...
```

Predictors register through the `katib.predictors` entry point and run in a separate process so a crash or out-of-memory error cannot take the server down.

Two uses:
- **Pre-label:** run a detector over selected images. Results arrive as `source = "model"` annotations with a confidence, shown in a distinct style until accepted.
- **Interactive segmentation:** click on an object and get a polygon (SAM-style). The frontend sends points, the predictor returns a mask, the server converts it to a simplified polygon.

**Licensing.** The `ultralytics` package is AGPL-3.0. Do not bundle it in the base package or the desktop installer. Support it as a separately installed plugin, and support ONNX models the user supplies. SAM 2 is Apache 2.0.

## 17. Frontend

TypeScript (strict), Svelte 5, Vite. Plain CSS driven by the tokens in `DESIGN.md`. No CSS framework.

```
web/src/
  lib/
    api/         generated client and types
    canvas/      annotation engine (framework-free)
      viewport.ts    zoom, pan, coordinate transforms
      renderer.ts    draws image and shapes
      hit.ts         hit testing, spatial index
      tools/         select, box, polygon, obb, keypoints, brush
      history.ts     command stack
    state/       Svelte stores: project, image, selection, session
    sync/        WebSocket client, offline outbox
    shortcuts/   registry, defaults, user remapping
    ui/          primitives: Button, Input, Chip, Modal, Menu, Toast, ...
  routes/        projects, workspace, inbox, settings
```

**The canvas engine has no Svelte in it.** It takes a canvas element, a list of shapes and callbacks, and can be unit-tested and reused. Svelte components wrap it.

**Rendering.** Two stacked canvases: the image layer, and an overlay for shapes and handles. The overlay redraws on demand through a dirty flag and `requestAnimationFrame`. Hit testing uses geometry directly, with an R-tree (`rbush`) once an image has more than about 500 shapes.

**Input.** Pointer Events for everything, so mouse, pen and touch share one code path. Touch adds pinch zoom, two-finger pan and larger hit targets. Tools are state machines with a common interface: `pointerDown`, `pointerMove`, `pointerUp`, `key`, `render`, `cursor`.

**Adding an annotation type** means adding a tool, a renderer branch, and a Details panel section. The tool registry keeps this to one folder.

**Sync and offline.** Edits are applied locally first, appended to an outbox in IndexedDB, and flushed in batches. The status indicator shows saved, saving, or "N pending" when offline. The outbox is the only place annotation data touches browser storage.

**Prefetching.** When an image opens, the next two images (and their annotations) are fetched in the background.

**State.** Server state (projects, images, annotations) is fetched and cached in stores, and WebSocket events invalidate or patch it. UI state (tool, zoom, selection) is local and never persisted to the server, except user preferences.

**Mobile.** Below 700px the side rails become a bottom sheet. See `DESIGN.md` for breakpoints and touch sizes. Phone annotation is optimized for review, quick boxes and tags. Precise polygon work is possible but not the target.

## 18. Configuration

One file, `katib.toml`, with environment overrides in the form `KATIB_SECTION__KEY`. Defaults work with no file.

```toml
[server]
host = "127.0.0.1"
port = 8420

[auth]
mode = "none"            # "none" (loopback only) or "local"
secret_key = ""          # generated on first run if empty

[database]
url = "sqlite:///{data_dir}/katib.db"

[storage]
backend = "local"
data_dir = ""            # platform default if empty
allowed_import_roots = []

[limits]
max_upload_mb = 50
max_image_pixels = 200_000_000
operation_retention_days = 30

[ml]
enabled = false
```

Data directory (via `platformdirs`): `katib.db`, `uploads/`, `thumbs/`, `operations/`, `logs/`.

## 19. Performance targets

Measured with `scripts/bench.py`, which seeds a synthetic project. Regressions fail CI once M2 lands.

| Area | Target |
|------|--------|
| Pan and zoom | 60 fps with 2,000 shapes on screen |
| Switch image | Under 150 ms with prefetch |
| Open a 100k-image project | Under 1 s to first paint (virtualized list) |
| Class merge or delete over 1M annotations | About 2 s |
| Rename class | Under 50 ms |
| Batch save of 50 ops | Under 100 ms |
| Import 1,000 images | Under 60 s including thumbnails |

Tools to get there: keyset pagination, indexes on `annotations(class_id)` and `images(project_id, status)`, `orjson`, thumbnails at import, ETag caching, HTTP range requests, canvas rendering.

## 20. Testing

- **Unit** (`pytest`): `core` geometry, format conversions, permission checks. Property tests (`hypothesis`) for coordinate conversions.
- **Formats:** golden files and round-trip tests for every format.
- **Services and API:** real database, no mocks. The suite runs on SQLite and Postgres in CI. Class operations are tested on both.
- **Concurrency:** tests for the task queue (two clients asking for `next`), locks and version conflicts.
- **Frontend unit** (`vitest`): the canvas engine (viewport math, hit testing, tools, history).
- **End to end** (`playwright`): create a project, import, draw, rename and merge a class, export, and a two-user flow. Runs at desktop and phone viewport sizes.
- **Bench:** the performance table above.

Every bug fix comes with a test that fails before the fix.

CI (GitHub Actions): lint, type check, import-linter, tests (SQLite and Postgres), web build, wheel build, Docker build. Tagged releases publish to PyPI and GHCR and build desktop installers.

## 21. Milestones

Each milestone ends with something that works and is committed. Do them in order.

**M0. Foundations**
Repo, `pyproject.toml`, CI, import-linter, layer skeleton, config loading, DB models and first migration, health endpoint, frontend shell with design tokens and theme toggle.
*Done when:* `katib` starts, serves the empty UI, and CI is green.

**M1. Single-user core**
Projects, folder and upload import, thumbnails, canvas with box and polygon tools, classes (create, rename, recolor), autosave with command-stack undo/redo, image list with filters, YOLO and COCO import and export.
*Done when:* you can label a real dataset and train on the export.

**M2. Class tools and dataset quality** (the differentiators)
Class manager with merge, delete-all and previews, aliases, operations log and revert, class gallery with bulk reclass and delete, attribute schemas, export splits and `data.yaml`, health panel (duplicates, tiny shapes, empties, imbalance, near-duplicate images).
*Done when:* merge and delete-all work at 1M annotations within target and can be reverted.

**M3. Multi-user**
Auth, roles, invites, "Next image" queue, assignment, soft locks, versions, WebSocket presence, review flow with comments, activity feed, Postgres support, Inbox screen.
*Done when:* three people label one project at once without stepping on each other.

**M4. Platforms**
Docker compose with Caddy, LAN share with QR and the HTTPS guidance, mobile layout and PWA, desktop wrapper and installers, workspace switcher (local, LAN, remote), offline outbox.
*Done when:* a phone and a desktop label the same project over the LAN.

**M5. More types and assistance**
Oriented boxes, keypoints, image-level tags, brush masks, more formats (VOC, LabelMe, YOLO OBB and segment, COCO keypoints), pre-label with a user model, interactive segmentation.

**M6. Hardening**
User docs site, Python SDK, benchmarks in CI, accessibility pass, i18n scaffolding with RTL, security review.

## 22. Non-goals

For now, and stated so they do not creep in:

- A native iOS or Android app (the PWA covers it).
- Sync between separate servers.
- Live co-editing of a single image.
- Video interpolation and tracking (image sequences only until v2).
- Text, audio, 3D and point cloud annotation.
- Parent/child class hierarchy (revisit as plain groups later).
- Enterprise SSO, billing, inter-annotator agreement metrics, active learning.
- Kubernetes manifests, a plugin marketplace, GraphQL.

## 23. Decisions log

Short records live in `docs/adr/NNNN-title.md` with: context, decision, consequences. Start with these:

- **ADR-001:** Synchronous services and routes, async only for WebSocket and streaming.
- **ADR-002:** SQLite by default, Postgres supported, one code path.
- **ADR-003:** Normalized geometry stored in JSON columns.
- **ADR-004:** Advisory soft locks plus per-annotation versions instead of real-time co-editing.
- **ADR-005:** One server as source of truth, no multi-master sync.
- **ADR-006:** Svelte 5 and plain CSS tokens, no CSS framework.
- **ADR-007:** ML predictors are optional plugins in separate processes (AGPL concern).

Add a new ADR whenever a decision here changes or a new one of similar weight is made.
