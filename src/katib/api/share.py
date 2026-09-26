"""Sharing: the addresses other devices use to reach this server, and a QR code for them."""

from fastapi import APIRouter, Request, Response

from katib import net
from katib.api.deps import AnywhereDep, UserDep, is_https
from katib.api.schemas import ShareOut
from katib.config import Settings, is_loopback
from katib.services.errors import Forbidden, InvalidInput

#: Where the Android app is published. Scanning this on a phone downloads it.
APP_DOWNLOAD_URL = "https://github.com/MergenEnBilge/Katib/releases/latest"

router = APIRouter(tags=["share"])

MAX_QR_TEXT = 300


def share_urls(request: Request) -> list[str]:
    """Addresses another device can use to reach this server, best first.

    The address someone set by hand wins. Otherwise the one this very request arrived on is used,
    because it demonstrably works. Asking the system for its own addresses is the last resort: in a
    container it answers with an address that only exists inside Docker.
    """
    settings: Settings = request.app.state.settings
    if settings.server.public_url:
        return [settings.server.public_url.rstrip("/")]

    # Listening on the loopback address means nobody else can reach this server, whatever address
    # the browser happens to have used.
    if is_loopback(settings.server.host):
        return []

    host = net.shareable_host(request.headers.get("host", ""))
    if host:
        scheme = "https" if is_https(request) else "http"
        return [f"{scheme}://{host}"]

    # Someone browsing from the server itself. On the machine we can work out its own addresses; in
    # a container we cannot see the host's, and a QR code leading nowhere is worse than none.
    if net.in_container():
        return []
    return [f"http://{a}:{settings.server.port}" for a in net.lan_addresses()]


@router.get("/share", response_model=ShareOut)
def share(request: Request, user: UserDep, anywhere: AnywhereDep) -> ShareOut:
    """Where to reach this server from a phone or another computer."""
    if not anywhere:
        raise Forbidden("Only an administrator can see how to share this server.")
    settings: Settings = request.app.state.settings
    urls = share_urls(request)
    return ShareOut(
        reachable=bool(urls),
        accounts=settings.auth.mode == "local",
        urls=urls,
        secure=bool(urls) and urls[0].startswith("https://"),
        app_url=APP_DOWNLOAD_URL,
        in_container=net.in_container(),
    )


@router.get("/share/qr.svg")
def qr(user: UserDep, anywhere: AnywhereDep, text: str) -> Response:
    if not anywhere:
        raise Forbidden("Only an administrator can make share codes.")
    if not text or len(text) > MAX_QR_TEXT:
        raise InvalidInput("That address is too long for a QR code.")
    return Response(net.qr_svg(text), media_type="image/svg+xml")
