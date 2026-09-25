"""Sharing: the addresses other devices use to reach this server, and a QR code for them."""

from fastapi import APIRouter, Request, Response

from katib import net
from katib.api.deps import AnywhereDep, UserDep
from katib.api.schemas import ShareOut
from katib.config import Settings, is_loopback
from katib.services.errors import Forbidden, InvalidInput

router = APIRouter(tags=["share"])

MAX_QR_TEXT = 300


@router.get("/share", response_model=ShareOut)
def share(request: Request, user: UserDep, anywhere: AnywhereDep) -> ShareOut:
    """Where to reach this server from a phone or another computer."""
    if not anywhere:
        raise Forbidden("Only an administrator can see how to share this server.")
    settings: Settings = request.app.state.settings
    reachable = not is_loopback(settings.server.host)
    urls: list[str] = []
    if settings.server.public_url:
        urls = [settings.server.public_url.rstrip("/")]
    elif reachable:
        urls = [f"http://{a}:{settings.server.port}" for a in net.lan_addresses()]
    return ShareOut(
        reachable=reachable or bool(settings.server.public_url),
        accounts=settings.auth.mode == "local",
        urls=urls,
        secure=bool(urls) and urls[0].startswith("https://"),
    )


@router.get("/share/qr.svg")
def qr(user: UserDep, anywhere: AnywhereDep, text: str) -> Response:
    if not anywhere:
        raise Forbidden("Only an administrator can make share codes.")
    if not text or len(text) > MAX_QR_TEXT:
        raise InvalidInput("That address is too long for a QR code.")
    return Response(net.qr_svg(text), media_type="image/svg+xml")
