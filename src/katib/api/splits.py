"""Routes for train, validation and test splits."""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from katib.api.class_ops import OperationOut, OpsStorage, operation_out
from katib.api.deps import SessionDep, UserDep, need
from katib.services import projects, splits

router = APIRouter(tags=["splits"])


class SplitConfigIn(BaseModel):
    ratios: dict[str, float] = Field(default_factory=dict)
    seed: int = 0
    stratify: bool = False


class SplitOut(BaseModel):
    counts: dict[str, int]
    ratios: dict[str, float]
    seed: int
    stratify: bool
    kind: str
    presets: dict[str, dict[str, float]]


class ShuffleIn(SplitConfigIn):
    only_unassigned: bool = False
    dry_run: bool = False


class ShuffleOut(BaseModel):
    dry_run: bool
    counts: dict[str, int]
    moved: int
    operation: OperationOut | None = None


class AssignIn(BaseModel):
    image_ids: list[uuid.UUID] = Field(max_length=10_000)
    split: str | None = None


class AssignOut(BaseModel):
    changed: int


def _state(session: SessionDep, project_id: uuid.UUID) -> SplitOut:
    config, kind = splits.get_config(session, project_id)
    return SplitOut(
        counts=splits.counts(session, project_id),
        ratios=config.ratios,
        seed=config.seed,
        stratify=config.stratify,
        kind=kind,
        presets=splits.presets(),
    )


@router.get("/projects/{project_id}/splits", response_model=SplitOut)
def get_splits(project_id: uuid.UUID, session: SessionDep, user: UserDep) -> SplitOut:
    need(session, user, project_id, "view")
    projects.get_project(session, project_id)
    return _state(session, project_id)


@router.put("/projects/{project_id}/splits", response_model=SplitOut)
def save_split_settings(
    project_id: uuid.UUID, body: SplitConfigIn, session: SessionDep, user: UserDep
) -> SplitOut:
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    splits.save_config(
        session, project_id, splits.SplitConfig(body.ratios, body.seed, body.stratify)
    )
    return _state(session, project_id)


@router.post("/projects/{project_id}/splits:shuffle", response_model=ShuffleOut)
def shuffle_splits(
    project_id: uuid.UUID,
    body: ShuffleIn,
    session: SessionDep,
    user: UserDep,
    storage: OpsStorage,
) -> ShuffleOut:
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    config = splits.SplitConfig(body.ratios, body.seed, body.stratify)
    if body.dry_run:
        chosen = splits.plan(session, project_id, config, only_unassigned=body.only_unassigned)
        return ShuffleOut(dry_run=True, counts=chosen.counts, moved=chosen.moved)
    chosen, op = splits.shuffle(
        session,
        storage,
        project_id,
        config,
        user_id=user.id,
        only_unassigned=body.only_unassigned,
    )
    return ShuffleOut(
        dry_run=False, counts=chosen.counts, moved=chosen.moved, operation=operation_out(op)
    )


@router.post("/projects/{project_id}/images:assign-split", response_model=AssignOut)
def assign_split(
    project_id: uuid.UUID, body: AssignIn, session: SessionDep, user: UserDep
) -> AssignOut:
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    return AssignOut(changed=splits.assign(session, project_id, body.image_ids, body.split))
