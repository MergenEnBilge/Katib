"""Image routes: import, list, and serving original files and thumbnails."""

import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from katib.api.deps import RunnerDep, SessionDep, StorageDep, UserDep, need
from katib.api.hub import emit
from katib.api.jobs import job_out
from katib.api.schemas import (
    FolderImportIn,
    HaveIn,
    HaveOut,
    ImageOut,
    ImagePageOut,
    ImagePatch,
    JobOut,
    LockOut,
)
from katib.db.models import User
from katib.jobs.runner import JobRunner
from katib.services import access, discussion, exchange, images, projects, tasks
from katib.services.errors import NotFound
from katib.services.images import ImageRow, StorageContext

router = APIRouter(tags=["images"])

CACHE = {"Cache-Control": "private, max-age=3600"}


def _file_etag(path: Path) -> str:
    stat = path.stat()
    return f'"{stat.st_mtime_ns}-{stat.st_size}"'


def _not_modified(request: Request, etag: str) -> bool:
    return request.headers.get("if-none-match") == etag


def _out(session: Session, row: ImageRow, me: User) -> ImageOut:
    out = ImageOut.model_validate(row.image)
    out.annotation_count = row.annotation_count
    held = tasks.lock_state(session, row.image)
    if held is not None and row.image.locked_by is not None and row.image.locked_until is not None:
        out.lock = LockOut(
            user_id=row.image.locked_by,
            name=str(held["name"]) if held["name"] else None,
            until=row.image.locked_until,
            mine=row.image.locked_by == me.id,
        )
    return out


@router.get("/projects/{project_id}/images", response_model=ImagePageOut)
def list_images(
    project_id: uuid.UUID,
    session: SessionDep,
    user: UserDep,
    status: str | None = None,
    q: str | None = None,
    has_annotations: bool | None = None,
    class_id: uuid.UUID | None = None,
    split: str | None = None,
    after: uuid.UUID | None = None,
    limit: int = 100,
) -> ImagePageOut:
    need(session, user, project_id, "view")
    projects.get_project(session, project_id)
    page = images.list_images(
        session,
        project_id,
        status=status,
        q=q,
        has_annotations=has_annotations,
        class_id=class_id,
        split=split,
        after=after,
        limit=limit,
    )
    return ImagePageOut(items=[_out(session, r, user) for r in page.rows], next=page.next)


@router.post("/projects/{project_id}/images:have", response_model=HaveOut)
def have_pictures(
    project_id: uuid.UUID, body: HaveIn, session: SessionDep, user: UserDep
) -> HaveOut:
    """Which of these pictures (by SHA-256) the project already has, so they need not be sent."""
    need(session, user, project_id, "manage")
    return HaveOut(have=images.known_digests(session, project_id, body.hashes))


@router.post("/projects/{project_id}/images", response_model=ImageOut, status_code=201)
def upload_image(
    project_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
) -> ImageOut:
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    image = images.import_upload(session, project_id, file.filename or "image", file.file, storage)
    return _out(session, ImageRow(image, 0), user)


def start_import(
    runner: JobRunner, storage: StorageContext, project_id: uuid.UUID, folder: str
) -> JobOut:
    """Index a folder in the background and return the job that tracks it."""
    # Fail fast on a bad folder so the person sees the reason now, not in a failed job.
    images.resolve_folder(folder, storage.allowed_roots)
    factory = runner.session_factory

    def work(progress: images.Progress) -> dict[str, object]:
        with factory() as s:
            report = images.import_folder(s, project_id, folder, storage, progress)
            # A folder that is already a labelled dataset gets its classes, splits and shapes
            # picked up in the same step, so nobody has to run Import labels by hand afterward
            # just because the pictures happened to already have annotation files beside them.
            dataset = exchange.detect_and_import(s, project_id, Path(folder))
            s.commit()
            # Files deleted or moved since the last scan, so nobody is left with broken pictures
            # and no idea why.
            missing = len(images.missing_in_folder(s, project_id, folder))
        return {
            "added": report.added,
            "missing": missing,
            "skipped": [{"name": k.name, "reason": k.reason} for k in report.skipped[:200]],
            "skipped_count": len(report.skipped),
            "dataset": asdict(dataset),
        }

    job_id = runner.submit("import_images", project_id, {"folder": folder}, work)
    job = runner.get(job_id)
    if job is None:
        raise NotFound("The import job could not be started.")
    return job_out(job)


@router.post("/projects/{project_id}/images:import-folder", response_model=JobOut, status_code=202)
def import_folder(
    project_id: uuid.UUID,
    body: FolderImportIn,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    runner: RunnerDep,
) -> JobOut:
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    return start_import(runner, storage, project_id, body.folder)


@router.get("/images/{image_id}", response_model=ImageOut)
def get_image(image_id: uuid.UUID, session: SessionDep, user: UserDep) -> ImageOut:
    need(session, user, access.project_of_image(session, image_id), "view")
    return _out(session, ImageRow(images.get_image(session, image_id), 0), user)


@router.patch("/images/{image_id}", response_model=ImageOut)
def update_image(
    image_id: uuid.UUID, body: ImagePatch, session: SessionDep, user: UserDep
) -> ImageOut:
    need(session, user, access.project_of_image(session, image_id), "annotate")
    image = tasks.transition(session, user, image_id, body.status)
    project_id = image.project_id
    emit(
        session.info,
        project_id,
        {"type": "image.status", "image_id": str(image_id), "status": image.status},
    )
    discussion.log(session, project_id, user, f"marked_{body.status}", {"image_id": str(image_id)})
    return _out(session, ImageRow(image, 0), user)


@router.get("/images/{image_id}/file")
def image_file(
    image_id: uuid.UUID, request: Request, session: SessionDep, user: UserDep, storage: StorageDep
) -> Response:
    need(session, user, access.project_of_image(session, image_id), "view")
    image = images.get_image(session, image_id)
    path = images.image_path(image, storage)
    etag = _file_etag(path)
    if _not_modified(request, etag):
        return Response(status_code=304, headers={**CACHE, "ETag": etag})
    return FileResponse(path, headers={**CACHE, "ETag": etag})


@router.get("/images/{image_id}/thumb")
def image_thumb(
    image_id: uuid.UUID, request: Request, session: SessionDep, user: UserDep, storage: StorageDep
) -> Response:
    need(session, user, access.project_of_image(session, image_id), "view")
    image = images.get_image(session, image_id)
    if image.kind == "text":
        raise NotFound("A text document has no thumbnail.")
    path = images.thumb_path(image, storage)
    etag = _file_etag(path)
    if _not_modified(request, etag):
        return Response(status_code=304, headers={**CACHE, "ETag": etag})
    return FileResponse(path, media_type="image/jpeg", headers={**CACHE, "ETag": etag})
