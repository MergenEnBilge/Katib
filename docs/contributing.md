# Contributing

## Set up

```bash
uv sync --all-extras
pnpm --dir web install
```

On Linux, `--all-extras` builds the GTK bindings the desktop window needs, so install these first:

```bash
sudo apt install build-essential pkg-config libgirepository1.0-dev libcairo2-dev gir1.2-webkit2-4.1
```

Run the app with live reload:

```bash
uv run katib dev              # backend on :8420, reloads on change
pnpm --dir web dev            # frontend on :5173, proxies /api to the backend
```

## How the code is laid out

The backend is Python with FastAPI and SQLAlchemy. `ARCHITECTURE.md` explains how the pieces fit together, and `DESIGN.md` describes the interface.

| Folder | What lives there |
|--------|------------------|
| `src/katib/core` | Plain logic with no input or output: geometry, run-length masks, detection decoding, quality checks |
| `src/katib/formats` | Readers and writers for each dataset format. They never touch the database |
| `src/katib/services` | The rules of the application, on top of the database |
| `src/katib/api` | HTTP routes, one file per area |
| `src/katib/db`, `storage`, `jobs`, `ml` | Database, files, background jobs and model runtime |
| `web/src/lib/canvas` | The drawing engine, which has no dependency on Svelte |
| `web/src/routes` | Screens and dialogs |
| `sdk` | The Python client |

The layers are enforced: `api` may use `services`, which may use `jobs`, then `db` and `storage`, then `core`. Run `uv run lint-imports` to check.

## Checks

Before you send a change, run:

```bash
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run lint-imports
uv run pytest
pnpm --dir web check && pnpm --dir web lint && pnpm --dir web test
```

Browser tests drive the real app at desktop and phone sizes, including an automated accessibility check:

```bash
pnpm --dir web build
pnpm --dir web exec playwright install chromium
pnpm --dir web exec playwright test
```

To run the Python tests against Postgres, point `KATIB_TEST_POSTGRES_URL` at a server and add `--db postgres`. Each test gets its own schema and cleans up after itself.

Speed targets are checked by `uv run python scripts/bench.py --check`.

After changing an API route, refresh the TypeScript types with `pnpm --dir web gen:api`.

## Changes

- Keep each commit to one change, with a plain message that says what it does.
- Every bug fix comes with a test that fails without the fix.
- Users' original images are never modified. Destructive operations show a preview, ask for confirmation and are recorded so they can be undone.
- No dependency under a copyleft license such as GPL or AGPL.

## Adding a language

Text lives in `web/src/lib/i18n/en.ts`. To add a language, copy that file, translate the values, and add an entry to `LOCALES` in `web/src/lib/i18n/index.svelte.ts` with the language code and its text direction. The language picker, the page direction and number and date formats follow from the entry. Keys you leave out fall back to English.

Two test languages help find problems before a real translation does. Open Katib with `?lang=qps-ploc` to see every translated string accented and lengthened, or `?lang=qps-plocm` for the same in a right-to-left layout. Text that stays plain English has not been moved into the message file yet.

## Adding a format

A format is a class with `id`, `label`, `supports`, `detect`, `read` and `write` (see `katib/core/dataset.py`). Add it to the list in `katib/formats/__init__.py`, or publish it as a plugin with the `katib.formats` entry point. Add golden files and a round-trip test.

## Building the docs

```bash
uv run --group docs mkdocs serve
```
