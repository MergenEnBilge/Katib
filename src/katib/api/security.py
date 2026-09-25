"""Response headers and the cross-site request check."""

from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import RequestResponseEndpoint

from katib.api.deps import SESSION_COOKIE, is_https

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}

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


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def _security(request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in UNSAFE and SESSION_COOKIE in request.cookies:
            origin = request.headers.get("origin")
            if origin and urlsplit(origin).netloc != request.headers.get("host", ""):
                return JSONResponse(
                    {
                        "code": "forbidden",
                        "message": "This request came from another site, so it was blocked.",
                        "details": {},
                    },
                    status_code=403,
                )
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
