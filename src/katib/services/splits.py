"""Train, validation and test splits kept on the images themselves.

A split is saved on each image, so it survives between exports and comes back on import. Shuffling
is deterministic for a seed, and every shuffle is written to the operations log so it can be undone.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from katib.core.split import PRESETS, SPLITS, SplitError, SplitItem, assign_splits
from katib.db.models import Annotation, Image, Operation, Project
from katib.services import class_ops
from katib.services.errors import InvalidInput, NotFound
from katib.storage.local import LocalStorage

CHUNK = 500


@dataclass(frozen=True)
class SplitConfig:
    """How a project likes its images divided. Saved so people do not retype it."""

    ratios: dict[str, float]
    seed: int = 0
    stratify: bool = False


@dataclass(frozen=True)
class SplitPlan:
    """What a shuffle would do, ready to preview or apply."""

    assignments: dict[uuid.UUID, str]
    counts: dict[str, int]
    moved: int


def kind_of(annotation_types: list[str]) -> str:
    """The kind of dataset a project is, from the shapes it draws. It picks the starting ratios."""
    for shape, kind in (
        ("obb", "obb"),
        ("mask", "segment"),
        ("polygon", "segment"),
        ("keypoints", "keypoints"),
        ("box", "detect"),
        ("tag", "tags"),
        ("text", "text"),
    ):
        if shape in annotation_types:
            return kind
    return "detect"


def _project(session: Session, project_id: uuid.UUID) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise NotFound("That project does not exist.")
    return project


def presets() -> dict[str, dict[str, float]]:
    return {kind: dict(ratios) for kind, ratios in PRESETS.items()}


def get_config(session: Session, project_id: uuid.UUID) -> tuple[SplitConfig, str]:
    """The saved split settings for a project, or the starting ratios for its kind of dataset."""
    project = _project(session, project_id)
    kind = kind_of(project.settings.get("annotation_types", []))
    saved: dict[str, Any] = project.settings.get("split") or {}
    ratios = {name: float(v) for name, v in (saved.get("ratios") or PRESETS[kind]).items()}
    return SplitConfig(ratios, int(saved.get("seed", 0)), bool(saved.get("stratify", False))), kind


def save_config(session: Session, project_id: uuid.UUID, config: SplitConfig) -> None:
    _check_ratios(config.ratios)
    project = _project(session, project_id)
    project.settings = {
        **project.settings,
        "split": {
            "ratios": {name: config.ratios.get(name, 0.0) for name in SPLITS},
            "seed": config.seed,
            "stratify": config.stratify,
        },
    }
    session.flush()


def _check_ratios(ratios: dict[str, float]) -> None:
    unknown = set(ratios) - set(SPLITS)
    if unknown:
        raise InvalidInput(f"Unknown split {sorted(unknown)[0]!r}. Use train, val or test.")
    if any(v < 0 for v in ratios.values()) or sum(ratios.values()) <= 0:
        raise InvalidInput("Split ratios must be positive numbers.")


def counts(session: Session, project_id: uuid.UUID) -> dict[str, int]:
    """Images in each split. `none` counts the ones not in any."""
    result = {name: 0 for name in SPLITS}
    result["none"] = 0
    rows = session.execute(
        select(Image.split, func.count(Image.id))
        .where(Image.project_id == project_id)
        .group_by(Image.split)
    )
    for name, n in rows:
        result[name if name in result else "none"] += n
    return result


def _current(
    session: Session, project_id: uuid.UUID, only_unassigned: bool, statuses: list[str] | None
) -> dict[uuid.UUID, str | None]:
    stmt = select(Image.id, Image.split).where(Image.project_id == project_id)
    if only_unassigned:
        stmt = stmt.where(Image.split.is_(None))
    if statuses:
        stmt = stmt.where(Image.status.in_(statuses))
    return {image_id: split for image_id, split in session.execute(stmt)}


def _classes_by_image(session: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, set[str]]:
    found: dict[uuid.UUID, set[str]] = {i: set() for i in ids}
    for start in range(0, len(ids), CHUNK):
        rows = session.execute(
            select(Annotation.image_id, Annotation.class_id)
            .where(
                Annotation.image_id.in_(ids[start : start + CHUNK]),
                Annotation.class_id.is_not(None),
            )
            .distinct()
        )
        for image_id, class_id in rows:
            found[image_id].add(str(class_id))
    return found


def plan(
    session: Session,
    project_id: uuid.UUID,
    config: SplitConfig,
    *,
    only_unassigned: bool = False,
    statuses: list[str] | None = None,
) -> SplitPlan:
    """Work out a split for the chosen images without saving anything."""
    _check_ratios(config.ratios)
    current = _current(session, project_id, only_unassigned, statuses)
    tally = {name: 0 for name in SPLITS}
    if not current:
        return SplitPlan({}, tally, 0)
    by_image = _classes_by_image(session, list(current)) if config.stratify else {}
    items = [SplitItem(str(i), frozenset(by_image.get(i, ()))) for i in current]
    try:
        chosen = assign_splits(items, config.ratios, config.seed, config.stratify)
    except SplitError as err:
        raise InvalidInput(str(err)) from err
    assignments = {uuid.UUID(k): v for k, v in chosen.items()}
    for name in assignments.values():
        tally[name] += 1
    moved = sum(1 for i, name in assignments.items() if current[i] != name)
    return SplitPlan(assignments, tally, moved)


def write_splits(session: Session, assignments: dict[uuid.UUID, str | None]) -> None:
    """Save a split (or none) on each image. Callers check the names."""
    by_split: dict[str | None, list[uuid.UUID]] = {}
    for image_id, name in assignments.items():
        by_split.setdefault(name, []).append(image_id)
    for name, ids in by_split.items():
        for start in range(0, len(ids), CHUNK):
            session.execute(
                update(Image)
                .where(Image.id.in_(ids[start : start + CHUNK]))
                .values(split=name, version=Image.version + 1)
            )


def shuffle(
    session: Session,
    operations: LocalStorage,
    project_id: uuid.UUID,
    config: SplitConfig,
    *,
    user_id: uuid.UUID | None = None,
    only_unassigned: bool = False,
    statuses: list[str] | None = None,
) -> tuple[SplitPlan, Operation]:
    """Save a new split on the chosen images and remember how they were, so it can be undone."""
    chosen = plan(session, project_id, config, only_unassigned=only_unassigned, statuses=statuses)
    if not chosen.assignments:
        raise InvalidInput("There are no images to split.")
    before = _current(session, project_id, only_unassigned, statuses)
    write_splits(session, dict(chosen.assignments))
    save_config(session, project_id, config)
    parts = ", ".join(f"{n:,} {name}" for name, n in chosen.counts.items() if n)
    op = class_ops.record(
        session,
        operations,
        project_id,
        user_id,
        "shuffle_splits",
        f"Split {len(chosen.assignments):,} images: {parts}.",
        {"before": {str(i): s for i, s in before.items()}},
    )
    return chosen, op


def assign(
    session: Session, project_id: uuid.UUID, image_ids: list[uuid.UUID], split: str | None
) -> int:
    """Put chosen images in a split by hand, or take them out with `None`."""
    if split is not None and split not in SPLITS:
        raise InvalidInput("Use train, val or test.")
    ids = [
        i
        for start in range(0, len(image_ids), CHUNK)
        for i in session.scalars(
            select(Image.id).where(
                Image.project_id == project_id, Image.id.in_(image_ids[start : start + CHUNK])
            )
        )
    ]
    write_splits(session, {i: split for i in ids})
    session.flush()
    return len(ids)
