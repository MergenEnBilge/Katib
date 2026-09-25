"""Settings routes: read them, change them, restart, and back up."""

import dataclasses
import os
import platform
import shutil
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from katib import restart
from katib.api.class_ops import OpsStorage
from katib.api.deps import RunnerDep, StorageDep, UserDep
from katib.api.jobs import job_out
from katib.api.schemas import JobOut
from katib.config import (
    Settings,
    read_data_dir_choice,
    read_saved,
    write_data_dir_choice,
    write_saved,
)
from katib.db.session import normalize_url
from katib.jobs.runner import Progress
from katib.services import app_settings, backup
from katib.services import class_ops as class_ops_service
from katib.services import folders as folders_service
from katib.services.errors import Forbidden, InvalidInput, NotFound
from katib.services.images import StorageContext
from katib.storage.imaging import set_pixel_limit

router = APIRouter(tags=["settings"])


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def require_manager(request: Request, user: UserDep) -> None:
    """On your own computer you run everything. On a shared server only administrators do."""
    if _settings(request).auth.mode != "none" and not user.is_admin:
        raise Forbidden("Only an administrator can change settings.")


AdminDep = Annotated[None, Depends(require_manager, scope="function")]


class OptionOut(BaseModel):
    value: str
    label: str


class FieldOut(BaseModel):
    key: str
    group: str
    label: str
    help: str
    kind: str
    live: bool
    minimum: int | None
    maximum: int | None
    options: list[OptionOut]
    allow_other: bool
    secret: bool
    value: Any
    running: Any
    source: str
    restart_pending: bool
    env_name: str | None


class GroupOut(BaseModel):
    id: str
    label: str
    help: str


class InfoOut(BaseModel):
    version: str
    python: str
    system: str
    data_dir: str
    database: str
    data_bytes: int
    free_bytes: int
    can_restart: bool
    restart_pending: bool


class SettingsOut(BaseModel):
    groups: list[GroupOut]
    fields: list[FieldOut]
    info: InfoOut


class SettingsIn(BaseModel):
    values: dict[str, Any]


class DatabaseTestIn(BaseModel):
    url: str


class DatabaseTestOut(BaseModel):
    ok: bool
    message: str


class Accepted(BaseModel):
    restarting: bool


def _folder_size(path: Path) -> int:
    total = 0
    for base, _dirs, names in os.walk(path):
        for name in names:
            try:
                total += (Path(base) / name).stat().st_size
            except OSError:
                continue
    return total


def _saved_view(settings: Settings) -> dict[str, dict[str, Any]]:
    """What is saved, including the data folder pointer that lives outside settings.json."""
    saved = read_saved(settings.data_dir)
    chosen = read_data_dir_choice()
    if chosen:
        saved.setdefault("storage", {})["data_dir"] = chosen
    return saved


def _payload(request: Request) -> SettingsOut:
    settings = _settings(request)
    started: app_settings.Snapshot = request.app.state.started
    states = app_settings.describe(settings, _saved_view(settings), started)
    fields = [
        FieldOut(
            key=s.field.key,
            group=s.field.group,
            label=s.field.label,
            help=s.field.help,
            kind=s.field.kind,
            live=s.field.live,
            minimum=s.field.minimum,
            maximum=s.field.maximum,
            options=[OptionOut(value=o.value, label=o.label) for o in s.field.options],
            allow_other=s.field.allow_other,
            secret=s.field.secret,
            value=s.value,
            running=s.running,
            source=s.source,
            restart_pending=s.restart_pending,
            env_name=s.env_name,
        )
        for s in states
    ]
    kind = "PostgreSQL" if settings.database_url.startswith("postgres") else "SQLite"
    free = shutil.disk_usage(settings.data_dir).free if settings.data_dir.exists() else 0
    info = InfoOut(
        version=version("katib"),
        python=platform.python_version(),
        system=f"{platform.system()} {platform.release()}",
        data_dir=str(settings.data_dir),
        database=kind,
        data_bytes=_folder_size(settings.data_dir),
        free_bytes=free,
        can_restart=bool(getattr(request.app.state, "can_restart", True)),
        restart_pending=any(f.restart_pending for f in fields),
    )
    return SettingsOut(
        groups=[GroupOut(id=g, label=label, help=h) for g, label, h in app_settings.GROUPS],
        fields=fields,
        info=info,
    )


@router.get("/settings", response_model=SettingsOut)
def read_settings(request: Request, _admin: AdminDep) -> SettingsOut:
    return _payload(request)


def _apply_live(
    request: Request, session_factory: Any, accepted: dict[str, Any], ops: OpsStorage
) -> None:
    """Apply the changes that do not need a restart to the running server."""
    settings = _settings(request)
    for key, value in accepted.items():
        field = app_settings.BY_KEY[key]
        if not field.live:
            continue
        setattr(getattr(settings, field.section), field.name, value)
    storage: StorageContext = request.app.state.storage
    if "limits.max_image_pixels" in accepted:
        set_pixel_limit(settings.limits.max_image_pixels)
    if "limits.max_upload_mb" in accepted:
        request.app.state.storage = dataclasses.replace(
            storage, max_upload_bytes=settings.limits.max_upload_mb * 1024 * 1024
        )
    if "storage.allowed_import_roots" in accepted:
        storage.allowed_roots[:] = [
            Path(r).expanduser() for r in settings.storage.allowed_import_roots
        ]
        with session_factory() as s:
            folders_service.load_connected(s, storage)
    if "limits.operation_retention_days" in accepted:
        with session_factory() as s:
            class_ops_service.purge_expired(s, ops, settings.limits.operation_retention_days)
            s.commit()


@router.put("/settings", response_model=SettingsOut)
def save_settings(
    body: SettingsIn, request: Request, _admin: AdminDep, ops: OpsStorage
) -> SettingsOut:
    settings = _settings(request)
    saved = read_saved(settings.data_dir)
    accepted = app_settings.check_changes(settings, _saved_view(settings), body.values)
    for key, value in accepted.items():
        field = app_settings.BY_KEY[key]
        if key == "storage.data_dir":
            write_data_dir_choice(value)
            continue
        saved.setdefault(field.section, {})[field.name] = value
    write_saved(settings.data_dir, saved)
    _apply_live(request, request.app.state.session_factory, accepted, ops)
    return _payload(request)


@router.post("/settings/test-database", response_model=DatabaseTestOut)
def test_database(body: DatabaseTestIn, request: Request, _admin: AdminDep) -> DatabaseTestOut:
    url = body.url.strip()
    if not url.startswith(("postgresql://", "postgres://", "sqlite:///")):
        raise InvalidInput("Enter an address that starts with postgresql:// or sqlite:///.")
    current = _settings(request).database.url
    if url == app_settings.mask(current):
        url = current
    engine = create_engine(normalize_url(url.replace("{data_dir}", "")), connect_args={})
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except (SQLAlchemyError, ModuleNotFoundError) as err:
        # The driver's message can hold the address, so show only the first line of the reason.
        reason = str(getattr(err, "orig", err)).strip().splitlines()[0] if str(err) else "failed"
        return DatabaseTestOut(ok=False, message=f"Could not connect: {reason}")
    finally:
        engine.dispose()
    return DatabaseTestOut(ok=True, message="Connected.")


@router.post("/settings/restart", response_model=Accepted, status_code=202)
def restart_katib(request: Request, _admin: AdminDep) -> Accepted:
    if not getattr(request.app.state, "can_restart", True):
        raise InvalidInput("Close Katib and open it again to apply these changes.")
    restart.restart_soon()
    return Accepted(restarting=True)


@router.post("/settings/backup", response_model=JobOut, status_code=202)
def start_backup(
    request: Request, _admin: AdminDep, runner: RunnerDep, storage: StorageDep
) -> JobOut:
    settings = _settings(request)
    backup.sqlite_file(settings.database_url)  # say now if this database cannot be backed up
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    name = f"katib-backup-{stamp}.zip"
    dest = storage.exports.path(name)

    def work(progress: Progress) -> dict[str, object]:
        report = backup.create(settings.data_dir, settings.database_url, dest, progress)
        return {"file": name, "files": report.files, "bytes": dest.stat().st_size}

    job_id = runner.submit("backup", None, {}, work)
    job = runner.get(job_id)
    if job is None:
        raise NotFound("The backup could not be started.")
    return job_out(job)
