"""One server per data folder, and how anything else on this computer finds it.

A running server holds an exclusive lock on `server.lock` in its data folder for as long as it
lives, so a second one cannot open the same database (two job runners would each fail the
other's work as interrupted). The operating system drops the lock when the process ends, however
it ends, so a crash never leaves the folder looking busy.

Once it answers, the server also writes `server.json` beside it: where it can be reached, and a
token that lets a program on this computer ask it to stop. The file is readable only by the
account that runs Katib, which is what keeps that token private.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import IO, Any

from katib.config import is_loopback

LOCK_NAME = "server.lock"
INFO_NAME = "server.json"
CONTROL_HEADER = "X-Katib-Control"


@dataclass(frozen=True)
class ServerInfo:
    pid: int
    #: The address a program on this computer should use, which is not always the bind address.
    url: str
    host: str
    port: int
    version: str
    token: str


def local_url(host: str, port: int) -> str:
    """Where a program on this same computer should connect. A wildcard bind answers on loopback
    too; only an address pinned to one interface has to be used as it is."""
    reach = "127.0.0.1" if host in ("0.0.0.0", "::") or is_loopback(host) else host
    return f"http://{reach}:{port}"


class InstanceLock:
    """An exclusive, non-blocking lock on `<data_dir>/server.lock`."""

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / LOCK_NAME
        self._file: IO[bytes] | None = None

    @property
    def held(self) -> bool:
        return self._file is not None

    def acquire(self) -> bool:
        if self._file is not None:
            return True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+b")  # noqa: SIM115 -- held open for the server's lifetime
        try:
            _lock(handle)
        except OSError:
            handle.close()
            return False
        self._file = handle
        return True

    def release(self) -> None:
        if self._file is None:
            return
        with contextlib.suppress(OSError):
            _unlock(self._file)
        self._file.close()
        self._file = None

    def acquire_within(self, seconds: float) -> bool:
        """Keep trying for a while. A restart starts the new copy before the old one has quite
        let go."""
        deadline = time.monotonic() + seconds
        while not self.acquire():
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.1)
        return True


if os.name == "nt":
    import msvcrt

    def _lock(handle: IO[bytes]) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock(handle: IO[bytes]) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock(handle: IO[bytes]) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(handle: IO[bytes]) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def lock_is_free(data_dir: Path) -> bool:
    """True when no server holds this data folder."""
    probe = InstanceLock(data_dir)
    if not probe.acquire():
        return False
    probe.release()
    return True


def write_info(data_dir: Path, info: ServerInfo) -> None:
    path = data_dir / INFO_NAME
    scratch = path.with_suffix(".tmp")
    scratch.write_text(json.dumps(asdict(info), indent=2), encoding="utf-8")
    with contextlib.suppress(OSError):  # not every file system has permissions
        scratch.chmod(0o600)
    scratch.replace(path)


def read_info(data_dir: Path) -> ServerInfo | None:
    try:
        raw: Any = json.loads((data_dir / INFO_NAME).read_text(encoding="utf-8"))
        return ServerInfo(
            pid=int(raw["pid"]),
            url=str(raw["url"]),
            host=str(raw["host"]),
            port=int(raw["port"]),
            version=str(raw["version"]),
            token=str(raw["token"]),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def remove_info(data_dir: Path) -> None:
    (data_dir / INFO_NAME).unlink(missing_ok=True)


def answers(url: str, timeout: float = 2.0) -> bool:
    """True when a Katib server answers its health check at `url`."""
    try:
        with urllib.request.urlopen(f"{url}/api/v1/health", timeout=timeout) as res:  # noqa: S310
            body: Any = json.loads(res.read())
    except (OSError, ValueError):
        return False
    return isinstance(body, dict) and "version" in body


def find_running(data_dir: Path) -> ServerInfo | None:
    """The server using this data folder, if one is up and answering."""
    info = read_info(data_dir)
    if info is None or lock_is_free(data_dir):
        return None
    return info if answers(info.url) else None


def wait_for(data_dir: Path, seconds: float) -> ServerInfo | None:
    """Wait for a server that is starting to answer."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        found = find_running(data_dir)
        if found is not None:
            return found
        time.sleep(0.2)
    return None


def stop(info: ServerInfo, data_dir: Path, seconds: float = 15.0) -> bool:
    """Ask a running server to stop, then wait until it has let go of its data folder."""
    request = urllib.request.Request(  # noqa: S310 -- always a URL this module wrote itself
        f"{info.url}/api/v1/server:stop",
        method="POST",
        headers={CONTROL_HEADER: info.token},
    )
    try:
        with urllib.request.urlopen(request, timeout=5):  # noqa: S310
            pass
    except OSError:
        return lock_is_free(data_dir)
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if lock_is_free(data_dir):
            return True
        time.sleep(0.2)
    return False
