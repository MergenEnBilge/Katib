#!/bin/sh
# Installs Katib on a Linux or macOS server that can run Docker.
#
#   curl -fsSL https://raw.githubusercontent.com/MergenEnBilge/Katib/main/install.sh | sh
#
# Options (add them after "sh -s --" when piping):
#   --photos DIR   a folder of pictures to label. Katib only reads it. Default: none
#   --port N       the port to serve on. Default: 8420
#   --name NAME    the container name. Default: katib
#   --yes          do not ask questions

set -eu

IMAGE="${KATIB_IMAGE:-ghcr.io/mergenenbilge/katib:v0.1.0-rc2}"
NAME="katib"
PORT="8420"
PHOTOS=""
ASSUME_YES="no"

say() { printf '%s\n' "$*"; }
fail() { printf 'Something went wrong: %s\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --photos) PHOTOS="${2:-}"; shift 2 ;;
    --port) PORT="${2:-}"; shift 2 ;;
    --name) NAME="${2:-}"; shift 2 ;;
    --yes) ASSUME_YES="yes"; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) fail "I do not know the option $1. Try --help." ;;
  esac
done

ask() {
  [ "$ASSUME_YES" = "yes" ] && return 0
  printf '%s [y/N] ' "$1"
  read -r answer < /dev/tty || return 1
  case "$answer" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

if ! command -v docker >/dev/null 2>&1; then
  say "Katib runs in Docker, and Docker is not installed on this machine."
  if ask "Install Docker now with the official script from get.docker.com?"; then
    curl -fsSL https://get.docker.com | sh || fail "Docker did not install."
  else
    say "Install Docker from https://docs.docker.com/get-docker/ and run this again."
    exit 1
  fi
fi

docker info >/dev/null 2>&1 || fail "Docker is installed but not running, or you need sudo. Try again with sudo."

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  say "A container called $NAME already exists."
  if ask "Replace it? Your projects are kept in the katib-data volume and are not deleted."; then
    docker rm -f "$NAME" >/dev/null
  else
    exit 1
  fi
fi

say "Downloading Katib..."
docker pull "$IMAGE" >/dev/null || fail "Could not download $IMAGE."

set -- -d --name "$NAME" --restart unless-stopped -p "$PORT:8420" -v katib-data:/data
if [ -n "$PHOTOS" ]; then
  [ -d "$PHOTOS" ] || fail "The folder $PHOTOS does not exist."
  set -- "$@" -v "$(cd "$PHOTOS" && pwd):/photos:ro"
fi
docker run "$@" "$IMAGE" >/dev/null || fail "Could not start Katib. Is port $PORT already in use?"

say "Starting..."
i=0
until docker exec "$NAME" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8420/api/v1/health')" >/dev/null 2>&1; do
  i=$((i + 1))
  [ "$i" -gt 60 ] && fail "Katib did not start. See what it says with: docker logs $NAME"
  sleep 1
done

CODE="$(docker exec "$NAME" cat /data/setup-code.txt 2>/dev/null || true)"
ADDRESS="$(hostname -I 2>/dev/null | cut -d' ' -f1 || true)"

say ""
say "Katib is running."
say "  On this machine:   http://localhost:$PORT"
[ -n "$ADDRESS" ] && say "  On your network:   http://$ADDRESS:$PORT"
say ""
say "Open it now and create the administrator account."
if [ -n "$CODE" ]; then
  say "If you open it from outside your own network, it asks for this setup code: $CODE"
fi
say ""
say "To stop it:      docker stop $NAME"
say "To update it:    run this installer again"
say "To back it up:   open Settings, then Backup, inside Katib"
[ -n "$PHOTOS" ] && say "Your photos are at /photos. Choose Connect a folder and pick it."
exit 0
