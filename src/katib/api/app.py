"""FastAPI application factory."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from katib.api import (
    annotations,
    app_settings,
    auth,
    class_ops,
    classes,
    errors,
    exchange,
    folders,
    health,
    images,
    jobs,
    ml,
    projects,
    quality,
    realtime,
    security,
    share,
    splits,
    tasks,
)
from katib.api.hub import Hub
from katib.api.serving import CompressApi, mount_ui
from katib.auth.ratelimit import LoginLimiter
from katib.config import Settings
from katib.db.migrate import upgrade_to_head
from katib.db.session import make_engine, make_session_factory
from katib.jobs.runner import JobRunner
from katib.services import app_settings as settings_service
from katib.services import auth as auth_service
from katib.services import class_ops as class_ops_service
from katib.services import folders as folders_service
from katib.services import setup_code
from katib.services.images import StorageContext
from katib.storage.imaging import set_pixel_limit
from katib.storage.local import LocalStorage

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app(settings: Settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        upgrade_to_head(settings.database_url)
        app.state.engine = make_engine(settings.database_url)
        app.state.session_factory = make_session_factory(app.state.engine)
        set_pixel_limit(settings.limits.max_image_pixels)
        app.state.storage = StorageContext(
            uploads=LocalStorage(settings.data_dir / "uploads"),
            thumbs=LocalStorage(settings.data_dir / "thumbs"),
            allowed_roots=[Path(r).expanduser() for r in settings.storage.allowed_import_roots],
            max_upload_bytes=settings.limits.max_upload_mb * 1024 * 1024,
            exports=LocalStorage(settings.data_dir / "exports"),
        )
        app.state.operations = LocalStorage(settings.data_dir / "operations")
        with app.state.session_factory() as s:
            folders_service.load_connected(s, app.state.storage)
            class_ops_service.purge_expired(
                s, app.state.operations, settings.limits.operation_retention_days
            )
            s.commit()
            if settings.auth.mode == "local" and not auth_service.has_users(s):
                log.warning(
                    "Katib is waiting for its first administrator. If you open it from outside "
                    "your own network you will be asked for the setup code: %s",
                    setup_code.get_or_create(settings.data_dir),
                )
        app.state.hub.bind(asyncio.get_running_loop())
        app.state.runner = JobRunner(app.state.session_factory)
        app.state.runner.fail_interrupted()
        log.info("Katib started, data in %s", settings.data_dir)
        yield
        app.state.runner.shutdown()
        app.state.engine.dispose()

    # The built-in /docs pages load scripts from a public CDN, which Katib's security headers
    # (and a machine with no internet) would block. /openapi.json is still served.
    app = FastAPI(title="Katib", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.started = settings_service.snapshot(settings)
    app.state.can_restart = True
    errors.install(app)
    security.install(app)
    app.state.limiter = LoginLimiter()
    app.state.hub = Hub()
    for module in (
        health,
        auth,
        projects,
        classes,
        class_ops,
        images,
        splits,
        app_settings,
        annotations,
        quality,
        tasks,
        exchange,
        folders,
        jobs,
        ml,
        realtime,
        share,
    ):
        app.include_router(module.router, prefix="/api/v1")
    mount_ui(app, STATIC_DIR)
    app.add_middleware(CompressApi)
    return app
