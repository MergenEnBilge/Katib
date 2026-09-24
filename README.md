# Katib

A self-hostable data annotation tool for images. Python backend, Svelte frontend, SQLite or Postgres.

Katib is under development and has no release yet. See `ARCHITECTURE.md` for how it works and `DESIGN.md` for how it looks.

## Run from source

```bash
uv sync
pnpm --dir web install
pnpm --dir web build
uv run katib
```

The server listens on `127.0.0.1:8420` and serves the built UI.

## Importing from a folder

Folder import indexes images where they are and never copies or changes them. Katib only reads folders you list in `katib.toml`:

```toml
[storage]
allowed_import_roots = ["/data/photos"]
```

Uploading from the browser needs no setup. Label files (YOLO folders with `data.yaml`, COCO `.json`) are read from the same allowed folders.

## End-to-end tests

```bash
pnpm --dir web build
pnpm --dir web exec playwright install chromium
pnpm --dir web exec playwright test
```

## Develop

```bash
uv run katib dev        # API with reload on :8420
pnpm --dir web dev      # Vite on :5173, proxies /api to :8420
```

Checks that must pass before a commit:

```bash
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run lint-imports
uv run pytest
pnpm --dir web check && pnpm --dir web lint && pnpm --dir web test
```
