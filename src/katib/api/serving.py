"""How the built interface and API replies are sent: cached hard, compressed once.

The interface's files have a hash in their name, so a copy can be kept for a year without ever
going stale. The page itself is checked every time, so a new version reaches people at once.
"""

import gzip
import mimetypes
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

IMMUTABLE = "public, max-age=31536000, immutable"
REVALIDATE = "no-cache"
SQUEEZABLE = {".js", ".css", ".svg", ".json", ".html", ".webmanifest", ".map", ".txt"}
MIN_SQUEEZE = 1024
# Replies that are already compressed or are files to save. Squeezing them wastes time.
NOT_JSON = ("/file", "/thumb", "/crop", "/download", "/qr.svg")


class CompressApi:
    """Gzip the API's JSON replies, and leave pictures, downloads and sockets alone."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.squeezed = GZipMiddleware(app, minimum_size=MIN_SQUEEZE)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope["path"].startswith("/api/")
            and not scope["path"].endswith(NOT_JSON)
        ):
            await self.squeezed(scope, receive, send)
        else:
            await self.app(scope, receive, send)


@lru_cache(maxsize=256)
def _squeezed(path: str, modified_ns: int) -> bytes:
    """A file's gzip form, made once per version of the file."""
    return gzip.compress(Path(path).read_bytes(), compresslevel=9)


def _cache_header(relative: str) -> str:
    return IMMUTABLE if relative.startswith("assets/") else REVALIDATE


def _send(request: Request, target: Path, relative: str) -> Response:
    headers = {"Cache-Control": _cache_header(relative), "Vary": "Accept-Encoding"}
    stat = target.stat()
    accepts = "gzip" in request.headers.get("accept-encoding", "")
    if accepts and target.suffix in SQUEEZABLE and stat.st_size >= MIN_SQUEEZE:
        body = _squeezed(str(target), stat.st_mtime_ns)
        return Response(
            body,
            media_type=mimetypes.guess_type(target.name)[0] or "application/octet-stream",
            headers={**headers, "Content-Encoding": "gzip", "ETag": f'"{stat.st_mtime_ns:x}-gz"'},
        )
    return FileResponse(target, headers=headers)


def mount_ui(app: FastAPI, static_dir: Path) -> None:
    """Serve the built interface, with index.html as the fallback for client-side routes."""
    index = static_dir / "index.html"
    if not index.is_file():
        return
    root = static_dir.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def ui(path: str, request: Request) -> Response:
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        target = (root / path).resolve()
        if path and target.is_file() and root in target.parents:
            return _send(request, target, path)
        return _send(request, index, "index.html")
