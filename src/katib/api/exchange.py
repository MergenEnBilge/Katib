"""Dataset import and export routes."""

import shutil
import uuid

from fastapi import APIRouter
from fastapi.responses import FileResponse

from katib.api.deps import RunnerDep, SessionDep, StorageDep, UserDep, need
from katib.api.jobs import job_out
from katib.api.schemas import DatasetImportIn, ExportIn, FormatOut, JobOut
from katib.core.dataset import ExportOptions, SplitSpec
from katib.formats import REGISTRY
from katib.jobs.runner import Progress
from katib.services import exchange, images, projects
from katib.services.errors import InvalidInput, NotFound

router = APIRouter(tags=["exchange"])


@router.get("/formats", response_model=list[FormatOut])
def list_formats(_user: UserDep) -> list[FormatOut]:
    return [
        FormatOut(id=f.id, label=f.label, supports=sorted(f.supports)) for f in REGISTRY.values()
    ]


@router.post("/projects/{project_id}/imports", response_model=JobOut, status_code=202)
def import_dataset(
    project_id: uuid.UUID,
    body: DatasetImportIn,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    runner: RunnerDep,
) -> JobOut:
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    path = images.resolve_path(body.path, storage.allowed_roots)
    factory = runner.session_factory

    def work(progress: Progress) -> dict[str, object]:
        with factory() as s:
            summary = exchange.import_dataset(s, project_id, path, body.format)
            s.commit()
        return {
            "format": summary.format_id,
            "images_matched": summary.images_matched,
            "unmatched_images": summary.unmatched_images,
            "shapes_added": summary.shapes_added,
            "classes_created": summary.classes_created,
            "notes": [{"subject": n.subject, "reason": n.reason} for n in summary.notes],
        }

    job_id = runner.submit("import_annotations", project_id, {"path": body.path}, work)
    job = runner.get(job_id)
    if job is None:
        raise NotFound("The import job could not be started.")
    return job_out(job)


@router.post("/projects/{project_id}/exports", response_model=JobOut, status_code=202)
def export_dataset(
    project_id: uuid.UUID,
    body: ExportIn,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    runner: RunnerDep,
) -> JobOut:
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    if body.format not in REGISTRY:
        raise InvalidInput(f"Unknown format {body.format!r}.")
    statuses: list[str] | None = [str(x) for x in body.statuses] if body.statuses else None
    if exchange.count_export(session, project_id, statuses) == 0:
        raise InvalidInput("There are no images to export with that filter.")
    factory = runner.session_factory
    split = None
    if body.split:
        ratios = {"train": body.split.train, "val": body.split.val, "test": body.split.test}
        split = SplitSpec(ratios, body.split.seed, body.split.stratify)
    opts = ExportOptions(copy_images=body.copy_images, split=split)

    def work(progress: Progress) -> dict[str, object]:
        name = f"{body.format}-{uuid.uuid4().hex[:12]}"
        folder = storage.exports.path(name)
        try:
            with factory() as s:
                report = exchange.export_dataset(
                    s, project_id, body.format, folder, storage, opts, statuses
                )
                s.commit()
            shutil.make_archive(str(storage.exports.path(name)), "zip", folder)
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        return {
            "file": f"{name}.zip",
            "images": report.images,
            "shapes": report.shapes,
            "notes": [{"subject": n.subject, "reason": n.reason} for n in report.notes],
        }

    job_id = runner.submit("export", project_id, {"format": body.format}, work)
    job = runner.get(job_id)
    if job is None:
        raise NotFound("The export job could not be started.")
    return job_out(job)


@router.get("/jobs/{job_id}/download")
def download_export(
    job_id: uuid.UUID, runner: RunnerDep, storage: StorageDep, session: SessionDep, user: UserDep
) -> FileResponse:
    job = runner.get(job_id)
    if job is None or job.kind != "export" or job.status != "done" or not job.result:
        raise NotFound("That export is not ready.")
    if job.project_id is not None:
        need(session, user, job.project_id, "manage")
    file = storage.exports.path(str(job.result["file"]))
    if not file.is_file():
        raise NotFound("That export file has been removed.")
    return FileResponse(file, media_type="application/zip", filename=file.name)


@router.get("/projects/{project_id}/export-info")
def export_info(project_id: uuid.UUID, session: SessionDep, user: UserDep) -> dict[str, object]:
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    return exchange.export_info(session, project_id)
