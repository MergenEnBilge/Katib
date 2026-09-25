# Running a server

## With Docker

This is the easiest way to run Katib for a team. It starts Katib, a Postgres database, and Caddy, which adds HTTPS.

```bash
cp .env.example .env
```

Open `.env` and set:

| Variable | What it is |
|----------|------------|
| `KATIB_DB_PASSWORD` | A long password for the database |
| `KATIB_PHOTOS` | The folder on the server with the photos to label. Katib only reads it |
| `KATIB_HOST` | The name people will type, such as `katib.example.com` or the server's address |
| `KATIB_TLS` | `internal` for a private network, or your email address for a public domain |

Then start it:

```bash
docker compose up -d
```

Open `https://` and that name. The first person to arrive creates the administrator account. In **Import images**, connect the folder called `/photos`.

### HTTPS

- On a **public domain**, set `KATIB_TLS` to your email address and Caddy gets a real certificate by itself.
- On a **private network**, leave it as `internal`. Caddy signs its own certificate, and each browser shows a warning once. To remove the warning, install Caddy's root certificate on those computers:

    ```bash
    docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./katib-root.crt
    ```

Katib is only reachable through Caddy. The compose file sets `server.behind_proxy`, so Katib trusts Caddy about who is visiting and that they used HTTPS. Do not set that option if anything other than your proxy can reach Katib directly.

### Upgrading

Pull the new code and run `docker compose up -d --build`. Migrations run at startup. Your data lives in Docker volumes, so it survives upgrades and `docker compose down`.

## Without Docker

Run `uv run katib serve --host 0.0.0.0` with accounts on, or `uv run katib share` for a quick local network setup. For anything beyond a trusted network, put a reverse proxy with HTTPS in front and set `server.behind_proxy = true`.

### Postgres

SQLite is fine for a team of a few people. For more, use Postgres:

```bash
uv sync --extra postgres
```

```toml
[database]
url = "postgresql://katib:secret@localhost/katib"
```

Katib creates its tables at startup.

## Settings

Every setting below can be changed from inside Katib. Choose **Settings** in the sidebar. Each one has a short explanation, and Katib checks what you type before it saves. A setting either applies straight away or shows **Needs a restart**. When something is waiting, a **Restart Katib now** button appears at the top. Katib restarts itself and reconnects your browser.

On a shared server, only administrators see the Settings page.

Katib keeps what you save in `settings.json` inside its data folder. If you would rather manage settings outside the app, for example in a Docker file, two other places work too:

- `katib.toml` in the folder you start Katib from.
- An environment variable in the form `KATIB_SECTION__KEY`, for example `KATIB_SERVER__PORT=9000`.

When the same setting appears in more than one place, the environment wins, then settings saved in the app, then `katib.toml`. A setting fixed by an environment variable shows a lock in the app, with the name of the variable, so nobody wonders why it will not change.

| Setting | Default | What it does |
|---------|---------|--------------|
| `server.host` | `127.0.0.1` | Address to listen on |
| `server.port` | `8420` | Port to listen on |
| `server.public_url` | none | The address people type, shown by the share window |
| `server.behind_proxy` | `false` | Trust a reverse proxy for the visitor's address and HTTPS |
| `auth.mode` | `none` | `none` for one person on one computer, `local` for accounts |
| `database.url` | SQLite in the data folder | Where projects are stored |
| `storage.data_dir` | Your user data folder | Where Katib keeps its database, thumbnails, uploads and undo history |
| `storage.allowed_import_roots` | none | Folders everyone on a shared server may import from |
| `limits.max_upload_mb` | `50` | Largest file the browser may upload |
| `limits.max_image_pixels` | `200000000` | Pictures with more pixels than this are refused |
| `limits.operation_retention_days` | `30` | How long bulk changes stay undoable |
| `ml.enabled` | `false` | Allow pre-labeling with your own model |
| `ml.models_dir` | `models` in the data folder | Where `.onnx` models live |

## Backups

The easy way: open **Settings**, then **Backup**, and choose **Make a backup**. You get one zip file with your projects, labels, settings and uploaded pictures. It works while people are using Katib. To put a backup back, close Katib and run:

```bash
katib restore your-backup.zip
```

Katib refuses to overwrite a database that is already there unless you add `--replace`, and then it keeps the old one beside it as `katib.db.before-restore`. Backups from the app cover the built-in database. For Postgres, use `pg_dump` as described below.

Everything Katib stores is in its data folder, plus the database if you use Postgres.

- **SQLite:** stop Katib and copy the data folder. Or, while it runs, copy the folder including the `katib.db-wal` file next to `katib.db`.
- **Postgres:** use `pg_dump` for the database, and copy the data folder for uploads and undo history.
- **Connected folders** are your own photos. Back them up the way you already do.

Thumbnails are cached and can be deleted safely. Katib makes them again when needed.

## Checking on it

`GET /api/v1/health` answers with the version and whether the database is reachable. The Docker image uses it for its health check. Logs go to standard output.
