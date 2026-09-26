"""Sharing: the addresses other devices use to reach this server, and a QR code for them."""

from dataclasses import dataclass, field

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


@dataclass(frozen=True)
class Reach:
    """How another device can reach this server."""

    urls: list[str] = field(default_factory=list[str])
    #: Katib is open to the network, but cannot work out which address to hand out. Someone has
    #: to tell it. Without this the share window would only be able to say "no", which is wrong.
    unknown: bool = False


def reach(request: Request) -> Reach:
    """Addresses another device can use to reach this server, best first.

    The address someone set by hand wins. Otherwise the one this very request arrived on is used,
    because it demonstrably works. Asking the system for its own addresses is the last resort: in a
    container it answers with an address that only exists inside Docker.
    """
    settings: Settings = request.app.state.settings
    if settings.server.public_url:
        return Reach([settings.server.public_url.rstrip("/")])

    # Listening on the loopback address means nobody else can reach this server, whatever address
    # the browser happens to have used.
    if is_loopback(settings.server.host):
        return Reach()

    host = net.shareable_host(request.headers.get("host", ""))
    if host:
        scheme = "https" if is_https(request) else "http"
        return Reach([f"{scheme}://{host}"])

    # Someone browsing from the server itself. On the machine we can work out its own addresses; in
    # a container we can only see the container's, which nothing outside Docker can reach.
    addresses = [] if net.in_container() else net.lan_addresses()
    if not addresses:
        return Reach(unknown=True)
    return Reach([f"http://{a}:{settings.server.port}" for a in addresses])


def share_urls(request: Request) -> list[str]:
    """Addresses another device can use to reach this server, best first."""
    return reach(request).urls


@router.get("/share", response_model=ShareOut)
def share(request: Request, user: UserDep, anywhere: AnywhereDep) -> ShareOut:
    """Where to reach this server from a phone or another computer."""
    if not anywhere:
        raise Forbidden("Only an administrator can see how to share this server.")
    settings: Settings = request.app.state.settings
    found = reach(request)
    return ShareOut(
        reachable=bool(found.urls),
        accounts=settings.auth.mode == "local",
        urls=found.urls,
        secure=bool(found.urls) and found.urls[0].startswith("https://"),
        app_url=APP_DOWNLOAD_URL,
        in_container=net.in_container(),
        needs_address=found.unknown,
        port=settings.server.port,
    )


@router.get("/share/qr.svg")
def qr(user: UserDep, anywhere: AnywhereDep, text: str) -> Response:
    if not anywhere:
        raise Forbidden("Only an administrator can make share codes.")
    if not text or len(text) > MAX_QR_TEXT:
        raise InvalidInput("That address is too long for a QR code.")
    return Response(net.qr_svg(text), media_type="image/svg+xml")
