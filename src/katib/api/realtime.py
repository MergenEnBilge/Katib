"""The WebSocket endpoint at /api/v1/ws?project=<id>."""

import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from katib.api.deps import find_user
from katib.api.hub import Conn, Hub
from katib.services import access
from katib.services.errors import KatibError

router = APIRouter()


def _identify(websocket: WebSocket, project_id: uuid.UUID) -> tuple[uuid.UUID, str] | None:
    """Resolve the caller and check they may view the project. Runs in a worker thread."""
    session = websocket.app.state.session_factory()
    try:
        user = find_user(websocket, session)
        if user is None:
            return None
        try:
            access.require(session, user, project_id, "view")
        except KatibError:
            return None
        session.commit()
        return user.id, user.name
    finally:
        session.close()


@router.websocket("/ws")
async def events(websocket: WebSocket, project: uuid.UUID) -> None:
    who = await run_in_threadpool(_identify, websocket, project)
    if who is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    hub: Hub = websocket.app.state.hub
    conn = Conn(websocket, who[0], who[1])
    await hub.join(project, conn)
    try:
        while True:
            message = await websocket.receive_json()
            kind = message.get("type") if isinstance(message, dict) else None
            if kind == "viewing":
                image_id = message.get("image_id")
                await hub.set_viewing(
                    project, conn, str(image_id) if isinstance(image_id, str) else None
                )
            elif kind == "ping":
                await websocket.send_json({"type": "pong"})
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        await hub.leave(project, conn)
