"""Image routes: import, list, and serving original files and thumbnails."""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse

from katib.api.deps import RunnerDep, SessionDep, StorageDep
from katib.api.jobs import job_out
from katib.api.schemas import FolderImportIn, ImageOut, ImagePageOut, ImagePatch, JobOut
from katib.services import images, projects
from katib.services.errors import NotFound
from katib.services.images import ImageRow

router = APIRouter(tags=["images"])

CACHE = {"Cache-Control": "private, max-age=3600"}


def _out(row: ImageRow) -> ImageOut:
    out = ImageOut.model_validate(row.image)
    out.annotation_count = row.annotation_count
    return out


@router.get("/projects/{project_id}/images", response_model=ImagePageOut)
def list_images(
    project_id: uuid.UUID,
    session: SessionDep,
    status: str | None = None,
    q: str | None = None,
    has_annotations: bool | None = None,
    class_id: uuid.UUID | None = None,
    after: uuid.UUID | None = None,
    limit: int = 100,
) -> ImagePageOut:
    projects.get_project(session, project_id)
    page = images.list_images(
        session,
        project_id,
        status=status,
        q=q,
        has_annotations=has_annotations,
        class_id=class_id,
        after=after,
        limit=limit,
    )
    return ImagePageOut(items=[_out(r) for r in page.rows], next=page.next)


@router.post("/projects/{project_id}/images", response_model=ImageOut, status_code=201)
def upload_image(
    project_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    session: SessionDep,
    storage: StorageDep,
) -> ImageOut:
    projects.get_project(session, project_id)
    image = images.import_upload(session, project_id, file.filename or "image", file.file, storage)
    return _out(ImageRow(image, 0))


@router.post("/projects/{project_id}/images:import-folder", response_model=JobOut, status_code=202)
def import_folder(
    project_id: uuid.UUID,
    body: FolderImportIn,
    session: SessionDep,
    storage: StorageDep,
    runner: RunnerDep,
) -> JobOut:
    projects.get_project(session, project_id)
    # Fail fast on a bad folder so the person sees the reason now, not in a failed job.
    images.resolve_folder(body.folder, storage.allowed_roots)
    factory = runner.session_factory

    def work(progress: images.Progress) -> dict[str, object]:
        with factory() as s:
            report = images.import_folder(s, project_id, body.folder, storage, progress)
        return {
            "added": report.added,
            "skipped": [{"name": k.name, "reason": k.reason} for k in report.skipped[:200]],
            "skipped_count": len(report.skipped),
        }

    job_id = runner.submit("import_images", project_id, {"folder": body.folder}, work)
    job = runner.get(job_id)
    if job is None:
        raise NotFound("The import job could not be started.")
    return job_out(job)


@router.get("/images/{image_id}", response_model=ImageOut)
def get_image(image_id: uuid.UUID, session: SessionDep) -> ImageOut:
    return _out(ImageRow(images.get_image(session, image_id), 0))


@router.patch("/images/{image_id}", response_model=ImageOut)
def update_image(image_id: uuid.UUID, body: ImagePatch, session: SessionDep) -> ImageOut:
    return _out(ImageRow(images.set_status(session, image_id, body.status), 0))


@router.get("/images/{image_id}/file")
def image_file(image_id: uuid.UUID, session: SessionDep, storage: StorageDep) -> FileResponse:
    image = images.get_image(session, image_id)
    return FileResponse(images.image_path(image, storage), headers=CACHE)


@router.get("/images/{image_id}/thumb")
def image_thumb(image_id: uuid.UUID, session: SessionDep, storage: StorageDep) -> FileResponse:
    image = images.get_image(session, image_id)
    return FileResponse(images.thumb_path(image, storage), media_type="image/jpeg", headers=CACHE)
