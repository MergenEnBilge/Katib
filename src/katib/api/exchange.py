"""Dataset import and export routes."""

import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from katib.api.deps import (
    AnywhereDep,
    RunnerDep,
    SessionDep,
    StorageDep,
    UserDep,
    may_browse_anywhere,
    need,
)
from katib.api.jobs import job_out
from katib.api.schemas import DatasetImportIn, ExportIn, FormatOut, JobOut
from katib.core.dataset import ExportOptions, SplitSpec
from katib.formats import REGISTRY, writes
from katib.jobs.runner import Progress
from katib.services import exchange, images, projects
from katib.services.errors import Forbidden, InvalidInput, NotFound

router = APIRouter(tags=["exchange"])

#: Files that name a dataset folder, so choosing one means the folder it sits in.
DATASET_FILE_NAMES = frozenset({"data.yaml", "data.yml", "obj.data"})


@router.get("/formats", response_model=list[FormatOut])
def list_formats(_user: UserDep) -> list[FormatOut]:
    return [
        FormatOut(id=f.id, label=f.label, supports=sorted(f.supports), can_export=writes(f))
        for f in REGISTRY.values()
    ]


@router.post("/projects/{project_id}/imports", response_model=JobOut, status_code=202)
def import_dataset(
    project_id: uuid.UUID,
    body: DatasetImportIn,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    runner: RunnerDep,
    anywhere: AnywhereDep,
) -> JobOut:
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    path = images.resolve_path(body.path, storage.allowed_roots, unrestricted=anywhere)
    # Someone who picked data.yaml or obj.data means the dataset folder it sits in.
    if path.is_file() and path.name.lower() in DATASET_FILE_NAMES:
        path = path.parent
    factory = runner.session_factory

    def work(progress: Progress) -> dict[str, object]:
        with factory() as s:
            summary = exchange.import_dataset(s, project_id, path, body.format)
            s.commit()
        return {
            "format": summary.format_id,
            "images_matched": summary.images_matched,
            "splits_set": summary.splits_set,
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
    anywhere: AnywhereDep,
) -> JobOut:
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    target = _export_target(body.destination, anywhere)
    if body.move_originals:
        if target is None:
            raise InvalidInput("Moving pictures needs a folder to move them into.")
        if not body.confirm_move:
            raise InvalidInput("Moving pictures needs your confirmation.")
    if body.format not in REGISTRY:
        raise InvalidInput(f"Unknown format {body.format!r}.")
    if not writes(REGISTRY[body.format]):
        raise InvalidInput(f"Katib reads {REGISTRY[body.format].label} but cannot export to it.")
    statuses: list[str] | None = [str(x) for x in body.statuses] if body.statuses else None
    if exchange.count_export(session, project_id, statuses) == 0:
        raise InvalidInput("There are no images to export with that filter.")
    factory = runner.session_factory
    split = None
    if body.split:
        ratios = {"train": body.split.train, "val": body.split.val, "test": body.split.test}
        split = SplitSpec(ratios, body.split.seed, body.split.stratify)
    # A move already puts the pictures in the export folder, so they are not copied as well.
    opts = ExportOptions(
        copy_images=body.copy_images and not body.move_originals,
        split=split,
        use_saved_splits=body.use_saved_splits,
    )

    def work(progress: Progress) -> dict[str, object]:
        if target is not None:
            return _export_to_folder(factory, project_id, body, target, storage, opts, statuses)
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


def _export_target(destination: str | None, anywhere: bool) -> Path | None:
    """The folder an export should be written into, or None for a zip download."""
    if not destination or not destination.strip():
        return None
    if not anywhere:
        raise Forbidden("Only an administrator can save an export to a folder on the server.")
    target = Path(destination.strip()).expanduser()
    if not target.parent.is_dir():
        raise InvalidInput("The folder above that one does not exist.")
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise InvalidInput("That folder already has files in it. Choose an empty or new folder.")
    return target


def _export_to_folder(
    factory: Any,
    project_id: uuid.UUID,
    body: ExportIn,
    target: Path,
    storage: StorageDep,
    opts: ExportOptions,
    statuses: list[str] | None,
) -> dict[str, object]:
    """Write the export straight into `target`. A failed export leaves no half-written folder."""
    created = not target.exists()
    try:
        with factory() as s:
            moved = (
                exchange.move_pictures(s, project_id, storage, target, statuses)
                if body.move_originals
                else []
            )
            s.commit()
            try:
                report = exchange.export_dataset(
                    s, project_id, body.format, target, storage, opts, statuses
                )
                s.commit()
            except BaseException:
                exchange.restore_pictures(moved)
                s.commit()
                raise
    except BaseException:
        if created:
            shutil.rmtree(target, ignore_errors=True)
        raise
    return {
        "file": None,
        "folder": str(target),
        "images": report.images,
        "shapes": report.shapes,
        "notes": [{"subject": n.subject, "reason": n.reason} for n in report.notes],
    }


@router.get("/jobs/{job_id}/download")
def download_export(
    job_id: uuid.UUID,
    request: Request,
    runner: RunnerDep,
    storage: StorageDep,
    session: SessionDep,
    user: UserDep,
) -> FileResponse:
    job = runner.get(job_id)
    if (
        job is None
        or job.kind not in ("export", "backup")
        or job.status != "done"
        or not job.result
    ):
        raise NotFound("That export is not ready.")
    if job.project_id is not None:
        need(session, user, job.project_id, "manage")
    elif job.kind == "backup" and not may_browse_anywhere(request, user):
        raise Forbidden("Only an administrator can download a backup.")
    file = storage.exports.path(str(job.result["file"]))
    if not file.is_file():
        raise NotFound("That export file has been removed.")
    return FileResponse(file, media_type="application/zip", filename=file.name)


@router.get("/projects/{project_id}/export-info")
def export_info(project_id: uuid.UUID, session: SessionDep, user: UserDep) -> dict[str, object]:
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    return exchange.export_info(session, project_id)
