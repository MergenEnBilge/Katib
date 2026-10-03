# Putting Katib where your team can reach it

Katib can run on your own computer, on a computer on your network, or on a server on the internet.
This guide covers the last two. You can change any of these choices later in **Settings**, so nothing
you decide here is permanent.

| What you want | Where to go |
|---------------|-------------|
| Label on my own computer | [Install Katib](getting-started.md) |
| Let colleagues on my network sign in | [One container](#one-container) |
| Run it on a Raspberry Pi or a small cloud server | [On a server or a Raspberry Pi](#on-a-server-or-a-raspberry-pi) |
| A full team setup with HTTPS | [The team setup with Docker Compose](#the-team-setup-with-docker-compose) |
| Reach it from the internet | [Over the internet](#over-the-internet) |

Each command in this guide is one line. Copy the whole line. Some guides break long commands over several
lines with a `\` at the end. That works in a Mac or Linux terminal, but PowerShell on Windows reads each
line as a separate command.

## One container

First, install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and open it. Then paste
this into PowerShell or Terminal:

```bash
docker run -d --name katib --restart unless-stopped -p 8420:8420 -v katib-data:/data ghcr.io/mergenenbilge/katib:v0.5.0
```

Open <http://localhost:8420>. Katib asks for a setup code before it creates the first account, because
whoever creates that account runs the server. To read the code, run:

```bash
docker exec katib cat /data/setup-code.txt
```

Paste the code in, create your account, and start labelling. The code stops working once the account
exists.

Katib starts again on its own whenever Docker starts. Your projects are kept in a Docker volume called
`katib-data`, which is separate from the container. Deleting the container does not delete your
projects.

To let someone else sign in, give them your computer's network address with `:8420` on the end.
**Settings**, then **Sharing**, shows the address. Then invite them from inside a project.

To label pictures that are already on your disk, mount that folder as well:

```bash
docker run -d --name katib --restart unless-stopped -p 8420:8420 -v katib-data:/data -v C:\Photos:/photos:ro ghcr.io/mergenenbilge/katib:v0.5.0
```

Then choose **Import**, then **Connect a folder**, and pick `/photos`. The `:ro` part makes the folder
read-only inside the container. Katib never changes your pictures, but the setting is a good safeguard.

!!! note "Who can reach it"

    `-p 8420:8420` makes Katib reachable from every network your computer is connected to. That suits a
    shared machine, but not a laptop on a public Wi-Fi network. If only you will use it, publish it to
    your own computer instead, with `-p 127.0.0.1:8420:8420`.

    Katib asks for the setup code in either case. From inside a container, Katib cannot tell how Docker
    shared the port, so it always asks.

Prefer not to use a terminal? In Docker Desktop, search for `mergenenbilge/katib`, choose **Run**, open
**Optional settings**, set the host port to `8420`, and add a volume named `katib-data` mounted at
`/data`.

## On a server or a Raspberry Pi

Any Linux computer that runs Docker will work. That includes a small cloud server, an old laptop, or a
Raspberry Pi 4 or newer. Run this on the machine itself:

```bash
curl -fsSL https://raw.githubusercontent.com/MergenEnBilge/Katib/main/install.sh | sh
```

The script checks for Docker and offers to install it if it is missing. It downloads Katib, starts it,
waits until it responds, and prints the address.

- To mount a folder of pictures, add `--photos /path/to/pictures`.
- If port 8420 is already in use, add `--port 9000`.

Open the printed address. Katib asks for a setup code before it creates the first account. The script
prints the code, and you can see it again later with `docker exec katib cat /data/setup-code.txt`. The
code stops anyone else on the network from claiming the server before you do.

To update, run the same command again. Your data is kept in the `katib-data` volume.

## The team setup with Docker Compose

Use this setup for a team that needs HTTPS and a proper database.

### How the pieces fit together

A single `docker run` starts one container. A team server needs three, and they have to work together:

- **katib**, the application.
- **db**, a Postgres database that stores your projects and labels.
- **caddy**, a web server that sits in front. It handles HTTPS and passes requests on to Katib.

A file called `docker-compose.yml` describes all three: which image each one uses, which folders they can
see, and what should restart. Compose reads that file and starts everything for you.

The three containers share a private network. Only Caddy is reachable from outside, on ports 80 and 443.
Katib and the database cannot be reached directly. There is one way in, and it uses HTTPS.

### Setting it up

You need the Katib code for this, because Compose reads `docker-compose.yml` and `docker/Caddyfile` from
disk:

```bash
git clone https://github.com/MergenEnBilge/Katib.git
cd Katib
cp .env.example .env
```

Open `.env` and fill in four values:

| Setting | What to enter |
|---------|---------------|
| `KATIB_DB_PASSWORD` | A long random string. You will not need to type it again |
| `KATIB_HOST` | The address people will type. Use `katib.example.com` on the internet, or the server's IP address on a private network |
| `KATIB_TLS` | `internal` on a private network. Your email address on a public domain |
| `KATIB_PHOTOS` | The folder on the server with the pictures to label. Leave it as it is if you do not have one yet |

Then start everything:

```bash
docker compose up -d
```

Open `https://` followed by your `KATIB_HOST`. The first person to arrive creates the administrator
account. Under **Import images**, connect the folder named `/photos`.

### Day-to-day commands

| Task | Command |
|------|---------|
| See what is running | `docker compose ps` |
| Read the logs | `docker compose logs -f katib` |
| Update | `docker compose pull`, then `docker compose up -d` |
| Stop everything | `docker compose down`. Your data stays in its volumes |
| Back up | In the app, go to **Settings**, then **Backup**. For the database, you can also run `pg_dump` |

## Over the internet

The steps above assume that people are on the same network as the server. To open Katib to the internet,
you need four things. Katib does not do any of them for you. Any self-hosted service needs the same
work.

### 1. A server with a public address

A small cloud server is the simplest choice. Two gigabytes of memory is enough to start, and most
providers offer one. It comes with a public IP address.

You can also host Katib at home, but it takes more effort. Your router has to forward ports 80 and 443 to
the machine. Your home IP address may change, and a dynamic DNS service can handle that. Some internet
providers block port 80 on home connections, which stops Caddy from getting a certificate. If that
happens, a cloud server is easier.

### 2. A domain name that points at it

Buy a domain name, or use one you already own. Add an **A record** for the name you want, such as
`katib.example.com`, and point it at the server's public IP address. DNS can take a few minutes to update.
Check it from your own computer:

```bash
nslookup katib.example.com
```

The answer should show your server's IP address. Nothing else will work until it does.

### 3. Open the firewall

Ports **80** and **443** must be reachable from the internet. Port 80 is needed even though Katib only
serves HTTPS. Caddy uses it to prove it controls the domain when it requests a certificate, and to send
visitors who type `http://` over to HTTPS.

Most cloud providers have a firewall or security group in their control panel. On the server itself, if
`ufw` is running:

```bash
sudo ufw allow 80,443/tcp
```

Do not open port 8420. Only Caddy should reach Katib.

### 4. Turn on real certificates

In `.env`, set:

```
KATIB_HOST=katib.example.com
KATIB_TLS=you@example.com
```

Then run `docker compose up -d`. Caddy requests a certificate from Let's Encrypt, usually within seconds.
It renews the certificate automatically while it runs, so you do not need to manage certificate files.

Open `https://katib.example.com`. Katib asks for the setup code before you create the first account:

```bash
docker compose exec katib cat /data/setup-code.txt
```

Create the administrator account, then invite your team from inside a project. Once that account exists,
the setup code no longer matters.

### Before you open it to the internet

Katib on the internet is a service you now look after. Keep these four things in mind:

- **Keep accounts turned on.** The Docker setup does this already. Katib also refuses to start on a network
  address without accounts.
- **Use strong passwords.** Whoever holds the administrator account can see every project on the server.
- **Keep a backup somewhere other than the server.** Go to **Settings**, then **Backup**, and save the zip
  file elsewhere. A copy on the same machine does not protect you if the machine fails.
- **Update regularly.** `docker compose pull && docker compose up -d` takes a few seconds. Updates include
  security fixes.

### On a private network

Set `KATIB_TLS=internal`, and Caddy makes its own certificate. HTTPS still works, but each browser warns
you once, because it does not know who issued the certificate. To remove the warning, copy Caddy's root
certificate and install it on the computers that need it:

```bash
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./katib-root.crt
```

This is also the setup you need for the iPhone home-screen app, which requires HTTPS.

## When something does not work

**The page does not open.** Check that the container is running with `docker ps`. Check that nothing else
is using port 8420. If it is, pick another port with `--port`.

**Katib asks for a setup code.** It asks everyone, because whoever creates the first account runs the
server. Run `docker exec katib cat /data/setup-code.txt`, or search for "setup code" in `docker logs katib`.

**Caddy does not get a certificate.** The cause is almost always DNS or the firewall. Check that the A
record points to the right IP address. Check that ports 80 and 443 are open from outside. Then read
`docker compose logs caddy`, which says what Caddy tried and what went wrong.

**A command fails on Windows with `invalid reference format`.** The command was split over several lines
with `\`. Paste it as one line.

**You want to start again.** `docker rm -f katib` removes the container and keeps your data. To delete the
data as well, run `docker volume rm katib-data`. This cannot be undone.
