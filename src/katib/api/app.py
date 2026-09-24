"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from katib.api import health
from katib.config import Settings
from katib.db.migrate import upgrade_to_head
from katib.db.session import make_engine, make_session_factory

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app(settings: Settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        upgrade_to_head(settings.database_url)
        app.state.engine = make_engine(settings.database_url)
        app.state.session_factory = make_session_factory(app.state.engine)
        log.info("Katib started, data in %s", settings.data_dir)
        yield
        app.state.engine.dispose()

    app = FastAPI(title="Katib", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health.router, prefix="/api/v1")
    _mount_ui(app)
    return app


def _mount_ui(app: FastAPI) -> None:
    """Serve the built frontend, with index.html as the fallback for client-side routes."""
    index = STATIC_DIR / "index.html"
    if not index.is_file():
        return

    @app.get("/{path:path}", include_in_schema=False)
    def ui(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        target = (STATIC_DIR / path).resolve()
        if path and target.is_file() and STATIC_DIR.resolve() in target.parents:
            return FileResponse(target)
        return FileResponse(index)
