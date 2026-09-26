# Put Katib where your team can reach it

Pick the way that matches what you have. You do not need to know how servers work for the first three.

| I want to... | Use | Time |
|--------------|-----|------|
| Label on my own computer | The [installer](getting-started.md) for Windows, macOS or Linux | 2 minutes |
| Share with people on my network | Docker Desktop, below | 5 minutes |
| Run it on a cloud server or a Raspberry Pi | The install script, below | 5 minutes |
| Use Katib from an Android phone | The `Katib-android.apk` from the releases page, which connects to your server | 2 minutes |
| Use Katib from an iPhone | Open your server in Safari and choose Add to Home Screen | 1 minute |
| Run it for a team with HTTPS and Postgres | [Running a server](server.md) | 15 minutes |

Everything you can set up here can be changed later from **Settings** inside Katib, so nothing you choose now is final.

## With Docker Desktop (Windows and macOS)

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and open it.
2. Open a terminal (PowerShell on Windows, Terminal on macOS) and paste:

    ```bash
    docker run -d --name katib --restart unless-stopped -p 8420:8420 -v katib-data:/data ghcr.io/mergenenbilge/katib:latest
    ```

3. Open <http://localhost:8420> and create the administrator account.

That is it. Katib starts again by itself when Docker does. To let a colleague in, send them the address shown under **Settings**, **Sharing**, using your computer's name or network address in place of `localhost`. Then invite them from inside a project.

To label pictures that are already on your computer, add a second folder to the command, for example `-v C:\Photos:/photos:ro`, and connect `/photos` from the **Import** window. The `:ro` means read only. Katib never changes your pictures.

Prefer no terminal? In Docker Desktop, search for `mergenenbilge/katib`, choose **Run**, open **Optional settings**, set the port to `8420`, and add a volume named `katib-data` at `/data`.

## On a server or a Raspberry Pi

Any Linux machine that can run Docker will do, from a small cloud server to a Raspberry Pi 4 or newer. Copy this into a terminal on the machine:

```bash
curl -fsSL https://raw.githubusercontent.com/MergenEnBilge/Katib/main/install.sh | sh
```

The script checks for Docker (and offers to install it), downloads Katib, starts it, waits until it answers, and prints the address. Add `--photos /path/to/pictures` to make a folder of pictures available, or `--port 9000` to use another port.

Open the address it prints. If you open it from outside your own network, Katib asks for a **setup code** before it lets you create the first account. This stops a stranger from claiming your server before you do. The script prints the code. You can also read it any time with `docker exec katib cat /data/setup-code.txt`.

To update, run the same command again. Your projects live in the `katib-data` volume and stay where they are.

## Docker Compose

If you like a file to keep in your notes, use one of the two we include:

```bash
docker compose -f docker-compose.simple.yml up -d
```

starts Katib alone, with its own small database. For a team with Postgres and automatic HTTPS, use `docker-compose.yml` as described in [Running a server](server.md).

## Before you open it to the internet

- **Use HTTPS.** Without it, passwords and labels cross the internet in the clear. The team setup includes Caddy, which gets a certificate for you. Details are in [Running a server](server.md#https).
- **Keep accounts on.** The Docker image starts with accounts turned on. Katib refuses to run without them on a network address.
- **Back up.** Choose **Settings**, then **Backup**, and keep the file somewhere else. See [Backups](server.md#backups).
- **Stay current.** Run the install command again, or `docker compose pull && docker compose up -d`, every so often.

## Something not working?

- *The page does not open.* Check that the container is running with `docker ps`, and that nothing else uses port 8420. Use `--port` to pick another.
- *It asks for a setup code and I have none.* Run `docker logs katib` and look for the line that says "setup code", or read `/data/setup-code.txt` as above.
- *I forgot which address to use.* Open **Settings**, then **Sharing** on the machine itself.
- *I need to start over.* `docker rm -f katib` stops it. Your data stays in the volume. `docker volume rm katib-data` deletes it for good.
