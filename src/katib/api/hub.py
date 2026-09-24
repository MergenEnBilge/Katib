"""In-process WebSocket hub: who is in a project, which image they have open, and change events.

Events are hints. Clients treat the REST API as the source of truth and refetch on reconnect.
A Redis adapter can sit behind the same interface when several workers are run (section 9).
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

log = logging.getLogger(__name__)


@dataclass
class Conn:
    socket: WebSocket
    user_id: uuid.UUID
    name: str
    image_id: str | None = None


@dataclass
class Hub:
    _rooms: dict[uuid.UUID, list[Conn]] = field(default_factory=dict[uuid.UUID, list[Conn]])
    _loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        """Remember the server's event loop so sync routes can publish from worker threads."""
        self._loop = loop

    def presence(self, project_id: uuid.UUID) -> list[dict[str, Any]]:
        return [
            {"user_id": str(c.user_id), "name": c.name, "image_id": c.image_id}
            for c in self._rooms.get(project_id, [])
        ]

    async def join(self, project_id: uuid.UUID, conn: Conn) -> None:
        self._rooms.setdefault(project_id, []).append(conn)
        await self.broadcast_presence(project_id)

    async def leave(self, project_id: uuid.UUID, conn: Conn) -> None:
        room = self._rooms.get(project_id, [])
        if conn in room:
            room.remove(conn)
        if not room:
            self._rooms.pop(project_id, None)
        await self.broadcast_presence(project_id)

    async def set_viewing(self, project_id: uuid.UUID, conn: Conn, image_id: str | None) -> None:
        conn.image_id = image_id
        await self.broadcast_presence(project_id)

    async def broadcast_presence(self, project_id: uuid.UUID) -> None:
        await self.broadcast(project_id, {"type": "presence", "users": self.presence(project_id)})

    async def broadcast(self, project_id: uuid.UUID, message: dict[str, Any]) -> None:
        for conn in list(self._rooms.get(project_id, [])):
            try:
                await conn.socket.send_json(message)
            except (RuntimeError, OSError):
                log.debug("Dropping a dead socket")
                room = self._rooms.get(project_id, [])
                if conn in room:
                    room.remove(conn)

    def publish(self, project_id: uuid.UUID, message: dict[str, Any]) -> None:
        """Send from a worker thread. Does nothing when nobody is listening."""
        loop = self._loop
        if loop is None or project_id not in self._rooms:
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(project_id, message), loop)


def emit(session_info: dict[str, Any], project_id: uuid.UUID, message: dict[str, Any]) -> None:
    """Queue an event on the session. It is published only after the transaction commits."""
    session_info.setdefault("events", []).append((project_id, message))
