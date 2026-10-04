# Running a server

This guide is for the person who keeps Katib running for a team. It covers Docker, backups, settings,
and day-to-day checks.

## With Docker

The Docker setup is the easiest way to run Katib for a team. It starts three containers: Katib, a
Postgres database, and Caddy, which provides HTTPS.

First, make your settings file:

```bash
cp .env.example .env
```

Open `.env` and fill in these values:

| Setting | What to put |
|---------|-------------|
| `KATIB_DB_PASSWORD` | A long password for the database. You will not need to type it again |
| `KATIB_PHOTOS` | The folder on the server that holds the pictures to label. Katib only reads from it |
| `KATIB_HOST` | The address people will type, such as `katib.example.com` or the server's IP address |
| `KATIB_TLS` | `internal` for a private network, or your email address for a public domain |

Then start Katib:

```bash
docker compose up -d
```

Open `https://` followed by the address you set. The first person to arrive creates the administrator
account. Under **Import images**, connect the folder named `/photos`.

### HTTPS

- **On a public domain**, set `KATIB_TLS` to your email address. Caddy gets a real certificate
  automatically.
- **On a private network**, leave `KATIB_TLS` as `internal`. Caddy makes its own certificate, and each
  browser shows a warning the first time. To remove the warning, install Caddy's root certificate on
  those computers:

    ```bash
    docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./katib-root.crt
    ```

Only Caddy can reach Katib. The compose file tells Katib to trust Caddy for the visitor's address and
for HTTPS. Do not turn on that setting if anything other than your proxy can reach Katib directly.

### Upgrading

Run `docker compose pull`, then `docker compose up -d`. Katib updates its database when it starts. Your
data is kept in Docker volumes, so it survives upgrades and `docker compose down`.

If you built the containers from source, pull the new code and run `docker compose up -d --build`.

## Without Docker

To run Katib directly, use one of these:

- `uv run katib serve --host 0.0.0.0` with accounts turned on.
- `uv run katib share` for a quick setup on your local network.

For anything beyond a network you trust, put a reverse proxy with HTTPS in front of Katib, and set
`server.behind_proxy = true`.

Only one server can run for each data folder. If you start a second one, it refuses and tells you
where the first one is listening. This protects the database from two servers writing to it at once.
To manage the server from another terminal on the same computer:

- `katib status` shows whether the server is running and where.
- `katib stop` stops it cleanly.
- `katib restore` will not run while the server is running.

### Postgres

SQLite works well for a small team. For a larger team, use Postgres:

```bash
uv sync --extra postgres
```

```toml
[database]
url = "postgresql://katib:secret@localhost/katib"
```

Katib creates its tables when it starts.

## Settings

You can change every setting from inside Katib. Choose **Settings** in the sidebar. Each setting has a
short explanation, and Katib checks what you enter before it saves.

Some settings take effect straight away. Others show **Needs a restart**. When a restart is needed, a
**Restart Katib now** button appears at the top of the page. Katib restarts itself, and your browser
reconnects.

On a shared server, only administrators can open the Settings page.

The **Sharing** section offers three choices: just you, your team on this network, or over the internet.
Each choice sets `auth.mode`, `server.host` and `server.behind_proxy` together. You can still change each
setting by hand.

Katib saves your settings in `settings.json` in its data folder. You can also manage them outside the
app, in one of these two places:

- `katib.toml` in the folder you start Katib from.
- Environment variables, written as `KATIB_SECTION__KEY`. For example, `KATIB_SERVER__PORT=9000`.

If the same setting appears in more than one place, the order of priority is: environment variables,
then settings saved in the app, then `katib.toml`. A setting that an environment variable controls shows
a lock in the app, with the variable's name, so you know why it cannot be changed there.

| Setting | Default | What it does |
|---------|---------|--------------|
| `server.host` | `127.0.0.1` | The address Katib listens on |
| `server.port` | `8420` | The port Katib listens on |
| `server.public_url` | none | The address people type. The Share window shows it |
| `server.behind_proxy` | `false` | Trust a reverse proxy for the visitor's address and for HTTPS |
| `auth.mode` | `none` | `none` for one person on one computer. `local` for accounts |
| `database.url` | SQLite in the data folder | Where projects are stored |
| `storage.data_dir` | Your user data folder | Where Katib keeps its database, thumbnails, uploads and undo history |
| `storage.allowed_import_roots` | none | Folders that everyone on a shared server may import from |
| `limits.max_upload_mb` | `100` | The largest picture a browser may upload |
| `limits.max_folder_upload_files` | `20000` | The most files in one folder upload |
| `limits.max_model_mb` | `500` | The largest model a browser may upload |
| `limits.max_image_pixels` | `200000000` | Pictures with more pixels than this are refused |
| `limits.operation_retention_days` | `30` | How long bulk changes can be undone |
| `ml.enabled` | `false` | Allow draft labels and click to select, using your own models |
| `ml.models_dir` | `models` in the data folder | Where `.onnx` model files are kept |

Under **Model help** you will also find two boxes for the two parts of a Segment Anything model, which
click to select needs. [Model help](assist.md) explains which model to use.

## Cloud buckets

Under **Settings**, then **Storage**, you can let this server read pictures from Amazon S3,
Cloudflare R2, Backblaze B2, MinIO, Google Cloud Storage or Azure Blob Storage. Katib tries the
details before saving them. See [Pictures in a cloud bucket](data.md#pictures-in-a-cloud-bucket).

Keys are kept in `cloud-sources.json` in the data folder, readable only by the account running
Katib. Use a key that can only read.

## People

With accounts turned on, **Settings**, then **People** lists everyone who has an account. Administrators
can create an account with a password, reset a password, make someone an administrator, and turn an
account off. Katib does not send email, so you give people their passwords yourself.

Turning off an account signs that person out straight away. Their name stays on the work they did.
Accounts cannot be deleted, because their labels would lose their author.

## Backups

The simplest way to back up is in the app. Open **Settings**, then **Backup**, and choose **Make a
backup**. You get one zip file that holds your projects, labels, settings and uploaded pictures. You can
make a backup while people are still working.

To restore a backup, close Katib and run:

```bash
katib restore your-backup.zip
```

Katib will not overwrite an existing database unless you add `--replace`. If you do, the old database is
saved next to the new one as `katib.db.before-restore`. Backups made in the app cover the built-in
database. If you use Postgres, back it up with `pg_dump`, as described below.

Everything Katib stores is in its data folder, plus the database if you use Postgres.

- **SQLite:** stop Katib, then copy the data folder. You can also copy it while Katib runs, as long as
  you include the `katib.db-wal` file next to `katib.db`.
- **Postgres:** use `pg_dump` for the database, and copy the data folder for the uploads and undo history.

## Starting over

Under **Settings**, then **Storage**, there is a **Reset everything** button in the danger zone. It
deletes the whole data folder, including every project, uploaded picture and saved setting. Katib then
starts the same first-run screen you saw on a new install.

Folders you only connected are not touched, because Katib never copied those pictures. The reset needs
you to type `RESET` to confirm, and it cannot be undone. Make a backup first if anything in the data
folder matters to you.

Thumbnails are stored in a cache. You can delete them safely. Katib makes them again when it needs them.

## Checking that it is running

`GET /api/v1/health` returns the version and whether the database is reachable. The Docker image uses it
to check the container. Logs are written to standard output.
