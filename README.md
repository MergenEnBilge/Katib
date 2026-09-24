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
