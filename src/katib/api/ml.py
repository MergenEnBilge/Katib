"""Model pre-labeling: which models are available and running one over a project."""

import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Request

from katib.api.class_ops import OpsStorage
from katib.api.deps import AnywhereDep, RunnerDep, SessionDep, StorageDep, UserDep, need
from katib.api.jobs import job_out
from katib.api.schemas import JobOut, MlModelOut, MlStatusOut, PrelabelIn
from katib.config import Settings
from katib.ml import onnx
from katib.services import prelabel, projects
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
            path = folder / name
            models.append(
                MlModelOut(name=name, classes=_class_names(str(path), path.stat().st_mtime))
            )
    return MlStatusOut(
        enabled=settings.ml.enabled,
        installed=installed,
        # Where files live on the server is only for the people who can put files there.
        models_dir=str(folder) if anywhere else "",
        models=models,
    )


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
        raise Forbidden(
            "Model pre-labeling is off. Set ml.enabled to true in katib.toml to use it."
        )
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
