"""Start, watch and stop one Katib server with its data folder held for it."""

from __future__ import annotations

import logging
import os
import secrets
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.metadata import version

import uvicorn

from katib.api.app import create_app
from katib.config import Settings
from katib.server import instance

log = logging.getLogger(__name__)

START_TIMEOUT_SECONDS = 30
#: How long a server waits for the data folder, which a restart's old copy may still be holding.
LOCK_WAIT_SECONDS = 10


class AlreadyRunning(Exception):
    """Another server already uses this data folder."""

    def __init__(self, url: str | None) -> None:
        self.url = url
        where = f" at {url}" if url else ""
        super().__init__(f"Katib is already running{where} for this data folder.")


class DidNotStart(Exception):
    """The server could not start, usually because its port is taken."""


def free_port(host: str, preferred: int) -> int:
    """The configured port if nothing on this interface uses it, so the address the Share window
    hands out is the one that answers. Falls back to any free port rather than refusing to start;
    the port actually used is what `server.json` and the Share window report."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, preferred))
        except OSError:
            probe.bind((host, 0))
        return int(probe.getsockname()[1])


@dataclass
class Control:
    """What the stop endpoint needs: a secret to check, and something to call."""

    token: str
    stop: Callable[[], None] = field(repr=False)


class ManagedServer:
    """One server, holding its data folder, that tells the rest of this computer where it is."""

    def __init__(self, settings: Settings, *, any_port: bool = False) -> None:
        """`any_port` lets the server take another port when its own is busy. Right for the
        desktop, where the window finds the server through `server.json`; wrong for `katib
        serve`, where a container's port mapping or a typed address expects exactly that port."""
        self.settings = settings
        self.any_port = any_port
        self.data_dir = settings.data_dir
        self.lock = instance.InstanceLock(self.data_dir)
        self.token = secrets.token_urlsafe(32)
        self.info: instance.ServerInfo | None = None
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    def _prepare(self) -> uvicorn.Server:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.lock.acquire_within(LOCK_WAIT_SECONDS):
            running = instance.read_info(self.data_dir)
            raise AlreadyRunning(running.url if running else None)
        try:
            return self._build()
        except BaseException:
            self.lock.release()
            raise

    def _build(self) -> uvicorn.Server:
        host = self.settings.server.host
        port = (
            free_port(host, self.settings.server.port)
            if self.any_port
            else self.settings.server.port
        )
        # The Share window reads this, so it hands out the port that actually answers.
        self.settings.server.port = port
        app = create_app(self.settings)
        app.state.control = Control(token=self.token, stop=self.stop)
        # log_config=None: uvicorn's own setup writes to the console, which a background server
        # does not have. Its messages reach Katib's handlers instead, a file or the terminal.
        # proxy_headers=False: Katib reads X-Forwarded-For itself, and only when server.behind_proxy
        # says to; uvicorn would otherwise believe it from any local caller.
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host=host,
                port=port,
                log_level="warning",
                log_config=None,
                proxy_headers=False,
            )
        )
        self._server = server
        self.info = instance.ServerInfo(
            pid=os.getpid(),
            url=instance.local_url(host, port),
            host=host,
            port=port,
            version=version("katib"),
            token=self.token,
        )
        return server

    def _announce_when_up(self, server: uvicorn.Server) -> None:
        deadline = time.monotonic() + START_TIMEOUT_SECONDS
        while not server.started:
            if server.should_exit or time.monotonic() > deadline:
                return
            time.sleep(0.05)
        if self.info is not None:
            instance.write_info(self.data_dir, self.info)
            log.info("Katib is running at %s", self.info.url)

    def _cleanup(self) -> None:
        instance.remove_info(self.data_dir)
        self.lock.release()

    def run_in_foreground(self) -> None:
        """Serve on this thread until stopped. Ctrl+C works, since uvicorn owns the signals."""
        server = self._prepare()
        threading.Thread(target=self._announce_when_up, args=(server,), daemon=True).start()
        try:
            server.run()
        finally:
            self._cleanup()

    def _serve(self, server: uvicorn.Server) -> None:
        # Let go of the folder the moment serving ends, so whoever asked it to stop -- the tray,
        # the window, `katib stop` -- sees it free without waiting for anyone to tidy up.
        try:
            server.run()
        finally:
            self._cleanup()

    def start(self) -> instance.ServerInfo:
        """Serve on a background thread and return once it answers."""
        server = self._prepare()
        self._thread = threading.Thread(
            target=self._serve, args=(server,), name="katib-server", daemon=True
        )
        self._thread.start()
        deadline = time.monotonic() + START_TIMEOUT_SECONDS
        while not server.started:
            if not self._thread.is_alive() or time.monotonic() > deadline:
                server.should_exit = True
                self._cleanup()
                raise DidNotStart(
                    f"Katib could not start on port {self.settings.server.port}. "
                    "Something else may be using it."
                )
            time.sleep(0.05)
        assert self.info is not None
        instance.write_info(self.data_dir, self.info)
        log.info("Katib is running at %s", self.info.url)
        return self.info

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def wait_until_stopped(self) -> None:
        """Block until a server started with `start` stops, however it was asked to, and has
        let go of its data folder."""
        if self._thread is not None:
            self._thread.join()

    def wait(self) -> None:
        self.wait_until_stopped()
        self._cleanup()  # in case it never got as far as serving
