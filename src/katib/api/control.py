"""Stopping a server that runs on its own, from another program on the same computer.

Whatever started the server puts a `control` on `app.state`: a secret token and a way to stop.
The token is in `server.json`, which only the account running Katib can read, so knowing it
proves the request comes from that account on this computer. Requests that do not come straight
from this computer are refused before the token is even looked at. A server started without a
control (in a test, or embedded somewhere) has nothing here to stop.
"""

import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Header, Request, Response

from katib.config import is_loopback
from katib.services.errors import Forbidden, NotFound

router = APIRouter(tags=["server"])


@router.post("/server:stop", status_code=202)
def stop_server(request: Request, x_katib_control: Annotated[str, Header()] = "") -> Response:
    control: Any = getattr(request.app.state, "control", None)
    if control is None:
        raise NotFound("This server cannot be stopped from here.")
    # The raw peer, deliberately not the address a proxy claims to be forwarding for.
    peer = request.client.host if request.client else ""
    if not is_loopback(peer):
        raise Forbidden("A server can only be stopped from the computer it runs on.")
    if not secrets.compare_digest(x_katib_control.encode(), str(control.token).encode()):
        raise Forbidden("That is not this server's control token.")
    control.stop()
    return Response(status_code=202)
