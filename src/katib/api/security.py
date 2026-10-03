"""Response headers, and the checks that keep other web pages away from Katib.

Two attacks matter for a server on someone's own computer:

- **Cross-site requests.** Any page the person visits can send a POST to 127.0.0.1. Browsers mark
  those with an Origin header, so an unsafe request whose Origin is not Katib's own is refused,
  with or without a session cookie: with accounts off there is no cookie, and the person counts
  as an administrator.
- **DNS rebinding.** A page on an attacker's domain re-points that domain at 127.0.0.1 and then
  talks to Katib as if it were its own site, which the Origin check cannot see. While Katib
  answers on loopback only, it refuses any request addressed to a host name other than a loopback
  one, so the attacker's name never reaches it.
"""

from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import RequestResponseEndpoint

from katib.api.deps import is_https
from katib.config import Settings, is_loopback

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}

#: Host names a loopback-only Katib answers to.
LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1"}

CSP = "; ".join(
    [
        "default-src 'self'",
        "img-src 'self' data: blob:",
        "style-src 'self' 'unsafe-inline'",
        "font-src 'self' data:",
        "connect-src 'self' ws: wss:",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
)


# Katib needs none of these, so no page may ask for them, even one that was injected.
PERMISSIONS = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()"


def _refuse(message: str) -> JSONResponse:
    return JSONResponse({"code": "forbidden", "message": message, "details": {}}, status_code=403)


def _host_name(host_header: str) -> str:
    """The name part of a Host header: `[::1]:8420` gives `::1`, `localhost:8420` `localhost`."""
    return urlsplit(f"//{host_header}").hostname or ""


def refusal(settings: Settings, host: str, origin: str | None, *, unsafe: bool) -> str | None:
    """Why a request should be refused, or None when it may go ahead. WebSockets count as unsafe:
    browsers send them across sites without asking."""
    if is_loopback(settings.server.host) and _host_name(host) not in LOOPBACK_NAMES:
        return (
            "Katib only answers this computer by the names localhost and 127.0.0.1, "
            "so a request addressed to another name was refused."
        )
    if unsafe and origin and urlsplit(origin).netloc != host:
        return "This request came from another site, so it was blocked."
    return None


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def _security(request: Request, call_next: RequestResponseEndpoint) -> Response:
        reason = refusal(
            request.app.state.settings,
            request.headers.get("host", ""),
            request.headers.get("origin"),
            unsafe=request.method in UNSAFE,
        )
        if reason:
            return _refuse(reason)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", PERMISSIONS)
        if is_https(request):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response
