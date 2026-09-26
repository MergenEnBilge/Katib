# Put Katib where your team can reach it

Katib runs in one of three places: your own computer, a machine on your network, or a server on the
internet. This page covers the last two. Everything here can be changed later from **Settings**, so
nothing you pick now is permanent.

| What you want | Where to go |
|---------------|-------------|
| Just label on my own machine | The [installer](getting-started.md) |
| Let colleagues on my network in | [One container](#one-container), below |
| Run it on a Raspberry Pi or a cloud box | [The install script](#on-a-server-or-a-raspberry-pi) |
| A proper team server with HTTPS | [Compose](#the-team-setup-docker-compose) |
| Reach it from anywhere on the internet | [Over the internet](#over-the-internet) |

A note on the commands below. They are written as one long line each. Copy the whole line. Some
guides split commands across several lines with a `\` at the end, which works in a Mac or Linux
terminal but breaks in PowerShell on Windows.

## One container

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/), open it, then paste this
into PowerShell or Terminal:

```bash
docker run -d --name katib --restart unless-stopped -p 8420:8420 -v katib-data:/data ghcr.io/mergenenbilge/katib:v0.1.0-rc3
```

Open <http://localhost:8420>. Create your account. You are labelling.

Katib comes back by itself whenever Docker starts. Your projects live in a Docker volume called
`katib-data`, separate from the container, so deleting the container does not touch them.

To let someone else in, give them your machine's network address with `:8420` on the end —
**Settings** then **Sharing** shows it — and invite them from inside a project.

To label pictures already on your disk, mount the folder as well:

```bash
docker run -d --name katib --restart unless-stopped -p 8420:8420 -v katib-data:/data -v C:\Photos:/photos:ro ghcr.io/mergenenbilge/katib:v0.1.0-rc3
```

Then choose **Import**, **Connect a folder**, and pick `/photos`. The `:ro` makes it read-only.
Katib never writes to your pictures anyway, but it costs nothing to be certain.

!!! warning "Who gets in first"

    `-p 8420:8420` publishes Katib on every network interface, and whoever opens it first creates
    the administrator account. On a shared or public network, create yours immediately. If Katib is
    only for you, bind it to your own machine instead: `-p 127.0.0.1:8420:8420`.

Prefer not to touch a terminal at all? In Docker Desktop, search for `mergenenbilge/katib`, choose
**Run**, open **Optional settings**, set the host port to `8420`, and add a volume named
`katib-data` mounted at `/data`.

## On a server or a Raspberry Pi

Any Linux machine that runs Docker will do — a £5 cloud box, an old laptop, a Raspberry Pi 4 or
newer. On the machine itself:

```bash
curl -fsSL https://raw.githubusercontent.com/MergenEnBilge/Katib/main/install.sh | sh
```

The script looks for Docker and offers to install it, downloads Katib, starts it, waits until it
answers, then prints the address. Add `--photos /path/to/pictures` to mount a folder, or
`--port 9000` if something already uses 8420.

Open the address it prints. Coming from outside your own network, Katib asks for a setup code before
it will create the first account — the script prints it, and `docker exec katib cat
/data/setup-code.txt` shows it again later. That code is what stops a stranger claiming your server
before you get to it.

Run the same command again to update. The `katib-data` volume is untouched.

## The team setup: Docker Compose

### What compose actually is

`docker run` starts one container. A real server needs three, and they have to find each other:

- **katib** — the app itself
- **db** — Postgres, which holds the projects and labels
- **caddy** — a web server that sits in front, terminates HTTPS and passes requests back to Katib

Compose is one file, `docker-compose.yml`, that describes all three: which image each uses, what
they are allowed to talk to, which folders and volumes they can see, and what to restart when. One
command reads that file and makes it so. You stop thinking about containers and start thinking about
the service.

The three containers share a private network that compose creates. Only Caddy publishes ports (80
and 443) to the outside world. Postgres and Katib are not reachable from outside at all — Katib
answers Caddy and nothing else. That is the point: one door, and it speaks HTTPS.

### Setting it up

You need the repository for this, because compose reads `docker-compose.yml` and `docker/Caddyfile`
from disk:

```bash
git clone https://github.com/MergenEnBilge/Katib.git
cd Katib
cp .env.example .env
```

Open `.env` and fill in four things:

| Variable | What to put |
|----------|-------------|
| `KATIB_DB_PASSWORD` | Any long random string. You will never type it again |
| `KATIB_HOST` | The name people will type. `katib.example.com` on the internet, or the server's IP on a private network |
| `KATIB_TLS` | `internal` on a private network. Your email address on a real domain |
| `KATIB_PHOTOS` | The folder on the server holding pictures to label. Leave it if you have none yet |

Then:

```bash
docker compose up -d
```

Open `https://` followed by your `KATIB_HOST`. The first person there creates the administrator
account. Under **Import images**, connect the folder called `/photos`.

### Day-to-day

| | |
|---|---|
| See what is running | `docker compose ps` |
| Read the logs | `docker compose logs -f katib` |
| Update | `docker compose pull` then `docker compose up -d` |
| Stop | `docker compose down` — your data stays in the volumes |
| Back up | **Settings**, **Backup** in the app. Also `pg_dump` the database if you want belt and braces |

## Over the internet

Everything above assumes people are on the same network as the server. Opening Katib to the internet
is four steps, and none of them are Katib's doing — this is the same work any self-hosted service
needs.

### 1. Get a machine with a public address

A small cloud server is the straightforward answer: 2 GB of memory is plenty to start, and any
provider will do. You get a public IP address with it.

Hosting from home works too, but there is more in the way. Your router has to forward ports 80 and
443 to the machine, your home IP probably changes every so often (a dynamic DNS provider fixes
that), and some ISPs block port 80 on residential lines, which stops Caddy getting a certificate.
If you hit that last one, a cloud box is less trouble than fighting it.

### 2. Point a domain at it

Buy a domain, or use one you have. Add an **A record** for the name you want — say
`katib.example.com` — pointing at the server's public IP address. Give DNS a few minutes, then
check from your own machine:

```bash
nslookup katib.example.com
```

You want your server's IP back. Nothing else will work until that is right.

### 3. Open the firewall

Ports **80** and **443** need to reach the server. Port 80 is not optional even though Katib only
serves HTTPS: Caddy uses it to prove it controls the domain when it asks for a certificate, and to
redirect visitors who type `http://`.

On a cloud provider this is a security group or firewall rule in their control panel. On the machine
itself, if `ufw` is running:

```bash
sudo ufw allow 80,443/tcp
```

Do **not** open 8420. Nothing should reach Katib except Caddy.

### 4. Tell compose the name and turn on real certificates

In `.env`:

```
KATIB_HOST=katib.example.com
KATIB_TLS=you@example.com
```

Then `docker compose up -d`. Caddy asks Let's Encrypt for a certificate, gets one within seconds,
and renews it on its own for as long as it keeps running. There is no certificate file to manage and
no renewal to remember.

Open `https://katib.example.com`. Because you are now arriving from a public address, Katib asks for
the setup code before it lets you create the first account:

```bash
docker compose exec katib cat /data/setup-code.txt
```

Create the administrator account, then invite your team from inside a project. Once that first
account exists, the code stops mattering.

### What to know before you do this

Katib on the internet is a service you are now responsible for. Four things are worth an hour of
your time:

Keep accounts on. The Docker image already does this, and Katib refuses to start on a network
address without them, but it is worth knowing why the guard exists.

Pick real passwords for the accounts you create, and remember that whoever holds the administrator
account can read every project on the server.

Back up somewhere that is not the server. **Settings**, then **Backup**, gives you a single zip. A
copy on the same machine is not a backup.

Update every so often. `docker compose pull && docker compose up -d` takes a few seconds, and it is
how security fixes reach you.

### On a private network instead

Leave `KATIB_TLS=internal` and Caddy signs its own certificate. HTTPS still works, but browsers warn
once per machine because nobody vouched for that certificate. To clear the warning, take Caddy's
root certificate and install it on the machines that need it:

```bash
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./katib-root.crt
```

This is also the route to take if you want the iPhone home-screen app, which needs HTTPS and will
not settle for plain `http`.

## When something does not work

**The page does not open.** Is the container running? `docker ps`. Is something else on port 8420?
Pick another with `--port`.

**It wants a setup code.** You are reaching it from outside its network, which is what that check is
for. `docker exec katib cat /data/setup-code.txt`, or look for "setup code" in `docker logs katib`.

**Caddy will not get a certificate.** Almost always DNS or the firewall. Check the A record resolves
to the right IP, check ports 80 and 443 are actually open from outside, then read
`docker compose logs caddy` — it says plainly what it tried and what happened.

**A command failed on Windows with `invalid reference format`.** You pasted a command split across
lines with `\`. PowerShell does not join lines that way. Paste it as one line.

**I want to start over.** `docker rm -f katib` removes the container and leaves your data.
`docker volume rm katib-data` deletes the data for good.
