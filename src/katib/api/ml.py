"""Model help: which models are available, pre-labeling a project, and click-to-select."""

import uuid
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile

from katib.api.class_ops import OpsStorage
from katib.api.deps import AnywhereDep, RunnerDep, SessionDep, StorageDep, UserDep, need
from katib.api.jobs import job_out
from katib.api.schemas import (
    JobOut,
    MlModelOut,
    MlStatusOut,
    ModelDownloadOut,
    PrelabelIn,
    SegmentIn,
    SegmentOut,
)
from katib.config import Settings
from katib.jobs.runner import Progress
from katib.ml import onnx, sam
from katib.services import images as images_service
from katib.services import model_downloads, prelabel, projects
from katib.services.errors import Forbidden, InvalidInput, NotFound

router = APIRouter(tags=["ml"])


@lru_cache(maxsize=16)
def _class_names(path: str, modified: float) -> list[str] | None:
    """A model's class names. Cached by file time, because reading them means loading the model."""
    try:
        return onnx.OnnxDetector(Path(path)).class_names
    except (onnx.ModelError, onnx.MlUnavailable):
        return None


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


@router.get("/ml", response_model=MlStatusOut)
def status(request: Request, user: UserDep, anywhere: AnywhereDep) -> MlStatusOut:
    settings = _settings(request)
    folder = settings.models_dir
    installed = onnx.is_available()
    models: list[MlModelOut] = []
    if settings.ml.enabled and installed:
        for name in onnx.list_models(folder):
            # The two halves of a Segment Anything model are not something to pre-label with.
            if name in (sam.ENCODER_NAME, sam.DECODER_NAME):
                continue
            path = folder / name
            models.append(
                MlModelOut(name=name, classes=_class_names(str(path), path.stat().st_mtime))
            )
    have = model_downloads.installed_id(folder)
    return MlStatusOut(
        enabled=settings.ml.enabled,
        installed=installed,
        # Where files live on the server is only for the people who can put files there.
        models_dir=str(folder) if anywhere else "",
        models=models,
        can_segment=settings.ml.enabled and installed and sam.is_installed(folder),
        downloads=[
            ModelDownloadOut(
                id=m.id, label=m.label, help=m.help, bytes=m.bytes, installed=m.id == have
            )
            for m in model_downloads.CATALOG
        ],
    )


#: What an uploaded file is. A detection model stands alone; the two halves of a Segment Anything
#: model have to be told apart, because nothing in the file itself says which is which.
KINDS = {"detect": "", "sam-encoder": sam.ENCODER_NAME, "sam-decoder": sam.DECODER_NAME}


@router.post("/ml/models", response_model=MlModelOut, status_code=201)
def upload_model(
    file: Annotated[UploadFile, File()],
    request: Request,
    user: UserDep,
    anywhere: AnywhereDep,
    kind: Annotated[str, Form()] = "detect",
) -> MlModelOut:
    """Add a model from the browser.

    Copying a file into the models folder is fine on your own machine, but the folder is inside the
    container when Katib runs in Docker, where there is nothing to drag it onto.
    """
    if not anywhere:
        raise Forbidden("Only an administrator can add a model.")
    if kind not in KINDS:
        raise InvalidInput("Choose what this file is: a detection model, or half of a SAM model.")
    name = Path(file.filename or "").name
    if not name.endswith(".onnx") or name.startswith("."):
        raise InvalidInput("A model must be a file ending in .onnx.")

    settings = _settings(request)
    folder = settings.models_dir
    folder.mkdir(parents=True, exist_ok=True)
    # The two halves of a SAM model are kept under names Katib chooses, so that uploading a
    # replacement is enough and nobody has to match up file names.
    fixed = KINDS[kind]
    if fixed:
        name = fixed
        # Replacing a half by hand means whatever was downloaded no longer matches what is on
        # disk, so it should stop being shown as installed.
        (folder / model_downloads.MARKER_NAME).unlink(missing_ok=True)
    destination = folder / name
    if destination.exists() and not fixed:
        raise InvalidInput(f"There is already a model called {name}. Rename it and try again.")

    size = 0
    limit = settings.limits.max_model_mb * 1024 * 1024
    with destination.open("wb") as out:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                out.close()
                destination.unlink(missing_ok=True)
                raise InvalidInput(f"A model may be at most {settings.limits.max_model_mb} MB.")
            out.write(chunk)

    if fixed or not onnx.is_available():
        return MlModelOut(name=name, classes=None)
    classes = _class_names(str(destination), destination.stat().st_mtime)
    return MlModelOut(name=name, classes=classes)


@router.post("/ml/models:download", response_model=JobOut, status_code=202)
def start_model_download(
    request: Request,
    user: UserDep,
    anywhere: AnywhereDep,
    runner: RunnerDep,
    model_id: Annotated[str, Form()],
) -> JobOut:
    """Fetch a model Katib knows about from the internet and install it.

    This is the one thing Katib ever asks the internet for on its own, and only when someone with
    access to this asks for it by name.
    """
    if not anywhere:
        raise Forbidden("Only an administrator can download a model.")
    source = model_downloads.find(model_id)
    folder = _settings(request).models_dir

    def work(progress: Progress) -> dict[str, object]:
        model_downloads.download_and_install(source, folder, progress)
        return {"id": source.id}

    job_id = runner.submit("model-download", None, {"model_id": source.id}, work)
    job = runner.get(job_id)
    if job is None:
        raise NotFound("The download could not be started.")
    return job_out(job)


@lru_cache(maxsize=1)
def _segmenter(folder: str, encoder_at: float, decoder_at: float) -> sam.SamSegmenter:
    """The loaded model, kept between requests. Uploading a new half makes a new one."""
    return sam.SamSegmenter(Path(folder))


@router.post("/projects/{project_id}/images/{image_id}/segment", response_model=SegmentOut)
def segment(
    project_id: uuid.UUID,
    image_id: uuid.UUID,
    body: SegmentIn,
    request: Request,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
) -> SegmentOut:
    """Outline whatever the clicks point at."""
    need(session, user, project_id, "annotate")
    settings = _settings(request)
    folder = settings.models_dir
    if not settings.ml.enabled:
        raise Forbidden("Model help is off. Turn it on under Settings, then Model help.")
    if not sam.is_installed(folder):
        raise InvalidInput(
            "No Segment Anything model has been added. "
            "Upload its image encoder and mask decoder under Settings, then Model help."
        )
    if not body.points:
        raise InvalidInput("Click on the thing you want outlined.")

    image = images_service.get_image(session, image_id)
    if image.project_id != project_id:
        raise NotFound("That image is not in this project.")
    path = images_service.image_path(image, storage)

    encoder = folder / sam.ENCODER_NAME
    decoder = folder / sam.DECODER_NAME
    try:
        model = _segmenter(str(folder), encoder.stat().st_mtime, decoder.stat().st_mtime)
        clicks = [sam.Click(x=p.x, y=p.y, positive=p.positive) for p in body.points]
        points = model.outline(path, str(image.id), clicks)
    except onnx.MlUnavailable as err:
        raise InvalidInput(str(err)) from err
    except onnx.ModelError as err:
        raise InvalidInput(str(err)) from err
    return SegmentOut(points=[[x, y] for x, y in points] if points else [])


@router.post("/projects/{project_id}/prelabel", response_model=JobOut, status_code=202)
def start(
    project_id: uuid.UUID,
    body: PrelabelIn,
    request: Request,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    runner: RunnerDep,
    operations: OpsStorage,
) -> JobOut:
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    settings = _settings(request)
    if not settings.ml.enabled:
        raise Forbidden("Model help is off. Turn it on under Settings, then Model help.")
    if not onnx.is_available():
        raise InvalidInput(
            "Pre-labeling needs an extra package. Install it with: uv sync --extra ml"
        )
    if body.model not in onnx.list_models(settings.models_dir):
        raise NotFound("That model is not in the models folder.")
    model_path = settings.models_dir / body.model
    factory = runner.session_factory
    user_id = user.id

    def work(progress: prelabel.Progress) -> dict[str, object]:
        detector = onnx.OnnxDetector(model_path)
        with factory() as s:
            result = prelabel.run(
                s,
                storage,
                operations,
                project_id,
                detector,
                threshold=body.threshold,
                only_unlabeled=body.only_unlabeled,
                create_missing_classes=body.create_missing_classes,
                class_names=body.class_names,
                user_id=user_id,
                progress=progress,
            )
        return {
            "images": result.images,
            "shapes": result.shapes,
            "skipped_classes": result.skipped_classes,
            "failed": result.failed[:50],
            "operation_id": str(result.operation.id) if result.operation else None,
        }

    job_id = runner.submit("prelabel", project_id, {"model": body.model}, work)
    job = runner.get(job_id)
    if job is None:
        raise NotFound("The pre-label job could not be started.")
    return job_out(job)
