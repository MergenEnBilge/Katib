"""Import and export of whole datasets through format plugins.

Formats work on plain dataclasses. This module maps them to and from the database: matching
images by filename, resolving class names and aliases, and streaming a project out.
"""

import shutil
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from katib.core.dataset import (
    ExportImage,
    ExportOptions,
    ExportReport,
    ImageLabels,
    Note,
    Shape,
    SkeletonSpec,
)
from katib.core.types import GeometryError, validate_geometry
from katib.db.ids import new_id
from katib.db.models import Annotation, Class, Image, Project, ProjectFolder
from katib.formats import UNRECOGNISED, FormatError, detect_format, get_format
from katib.formats.yolo import yaml_covers
from katib.services import classes, splits
from katib.services.errors import InvalidInput, NotFound
from katib.services.folders import allow_folder
from katib.services.images import FILE_PREFIX, StorageContext, image_path

CHUNK = 200
MAX_NOTES = 200


@dataclass
class ImportSummary:
    format_id: str
    images_matched: int = 0
    splits_set: int = 0
    shapes_added: int = 0
    classes_created: list[str] = field(default_factory=list[str])
    unmatched_images: int = 0
    notes: list[Note] = field(default_factory=list[Note])


def import_dataset(
    session: Session, project_id: uuid.UUID, path: Path, format_id: str | None = None
) -> ImportSummary:
    """Read a dataset and attach its shapes to matching images in one transaction.

    Images are matched by filename, or by name without extension when the format only has stems
    (YOLO). Images that already have shapes are left alone so importing twice cannot duplicate
    them. Class names resolve through names and aliases, and unknown names become new classes.
    """
    sizes = {
        Path(name).stem.lower(): (width, height)
        for name, width, height in session.execute(
            select(Image.filename, Image.width, Image.height).where(Image.project_id == project_id)
        )
    }
    try:
        fmt = get_format(format_id) if format_id else detect_format(path)
        parsed = fmt.read(path, sizes)
    except FormatError as err:
        raise InvalidInput(str(err)) from err

    summary = ImportSummary(format_id=fmt.id, notes=list(parsed.notes))
    class_ids: dict[str, uuid.UUID] = {}
    for name in parsed.class_names:
        cls = classes.resolve_class(session, project_id, name)
        if cls is None:
            cls = classes.create_class(session, project_id, name)
            summary.classes_created.append(cls.name)
        class_ids[name] = cls.id
        spec = parsed.skeletons.get(name)
        if spec is not None and cls.skeleton is None:
            classes.set_skeleton(session, cls.id, spec.names, spec.edges)

    by_full_name: dict[str, list[Image]] = {}
    by_stem: dict[str, list[Image]] = {}
    for img in session.scalars(select(Image).where(Image.project_id == project_id)):
        by_full_name.setdefault(img.filename.lower(), []).append(img)
        by_stem.setdefault(Path(img.filename).stem.lower(), []).append(img)
    has_shapes = set(
        session.scalars(
            select(Annotation.image_id)
            .join(Image, Image.id == Annotation.image_id)
            .where(Image.project_id == project_id)
            .distinct()
        )
    )

    for labels in parsed.images:
        key = labels.filename.lower()
        candidates = by_full_name.get(key) or by_stem.get(Path(key).stem, [])
        image = _pick(candidates, labels)
        if image is None:
            if len(candidates) > 1:
                summary.notes.append(
                    Note(labels.filename, "More than one image has this name, in the same place.")
                )
            summary.unmatched_images += 1
            continue
        # What the dataset says outright -- a split list, a per-split annotation file -- is more
        # reliable than a guess from folder names made when the picture was added.
        if labels.split and image.split != labels.split:
            image.split = labels.split
            summary.splits_set += 1
        if image.id in has_shapes:
            summary.notes.append(Note(labels.filename, "Already has shapes, so it was skipped."))
            continue
        summary.images_matched += 1
        for shape in labels.shapes:
            try:
                geometry = validate_geometry(shape.type, shape.geometry).model_dump()
            except GeometryError as err:
                summary.notes.append(Note(labels.filename, str(err)))
                continue
            session.add(
                Annotation(
                    id=new_id(),
                    image_id=image.id,
                    class_id=class_ids.get(shape.class_name),
                    type=shape.type,
                    geometry=geometry,
                    attrs=shape.attrs,
                    source="import",
                )
            )
            summary.shapes_added += 1
    session.flush()
    del summary.notes[MAX_NOTES:]
    return summary


_SPLIT_WORDS = {"train", "training", "val", "valid", "validation", "dev", "test", "testing"}
_PLUMBING = {"images", "image", "labels", "label", "annotations", "jpegimages", "img", "imgs"}


def _folders_of(image: Image) -> list[str]:
    """The folders a picture read in place sits in, lowercased, nearest last."""
    if not image.storage_key.startswith(FILE_PREFIX):
        return []
    return [p.lower() for p in Path(image.storage_key[len(FILE_PREFIX) :]).parent.parts]


def _pick(candidates: list[Image], labels: ImageLabels) -> Image | None:
    """Which of several same-named pictures a label belongs to.

    One is easy. Several -- a.jpg in both train and val, the usual case -- are told apart first by
    the split the dataset gives the label, then by the folders the label sat in, matched against
    the folders each picture sits in. Folders such as "images" and "labels" say nothing, since
    every split has them; the rest ("train", a class or a batch name) do.
    """
    if len(candidates) <= 1:
        return candidates[0] if candidates else None
    if labels.split:
        same_split = [c for c in candidates if c.split == labels.split]
        if len(same_split) == 1:
            return same_split[0]
        if same_split:
            candidates = same_split
    hints = [f.lower() for f in labels.folders if f.lower() not in _PLUMBING]
    if not hints:
        return None

    def score(image: Image) -> int:
        folders = _folders_of(image)
        return sum(1 for h in hints if h in folders)

    ranked = sorted(candidates, key=score, reverse=True)
    best = score(ranked[0])
    if best == 0 or score(ranked[1]) == best:
        return None
    return ranked[0]


@dataclass
class DatasetOutcome:
    """What connecting a folder found: a dataset that was read, no dataset, or one that failed."""

    state: str  # "read", "none" or "failed"
    format: str | None = None
    reason: str | None = None
    images_matched: int = 0
    shapes_added: int = 0
    classes_created: list[str] = field(default_factory=list[str])
    splits_set: int = 0
    unmatched_images: int = 0
    notes: list[dict[str, str]] = field(default_factory=list[dict[str, str]])


def _dataset_folders(path: Path) -> list[Path]:
    """The chosen folder, then the two above it: a dataset's data.yaml can sit higher up."""
    return [path, *list(path.parents)[:2]]


def detect_and_import(session: Session, project_id: uuid.UUID, path: Path) -> DatasetOutcome:
    """If `path` already holds a recognized dataset, read its classes, splits and shapes too.

    Connecting a folder normally only adds pictures. Plenty of folders people connect are already
    a finished dataset: a `data.yaml` next to the labels, a COCO `annotations.json`, Pascal VOC
    XML, or LabelMe JSON. This only ever adds to what connecting the folder already did, never
    instead of it. The outcome says which of three things happened, so the job can show it.

    A YOLO `data.yaml` in a folder above the chosen one is used only when it lists the chosen
    folder as one of its splits, so an unrelated file higher up is never picked up.
    """
    problem: str | None = None
    for candidate in _dataset_folders(path):
        if candidate != path and not yaml_covers(candidate, path):
            continue
        try:
            fmt = detect_format(candidate)
        except FormatError as err:
            if str(err) != UNRECOGNISED:
                problem = problem or str(err)
            continue
        try:
            summary = import_dataset(session, project_id, candidate, fmt.id)
        except InvalidInput as err:
            return DatasetOutcome("failed", fmt.id, err.message)
        return DatasetOutcome(
            "read",
            summary.format_id,
            images_matched=summary.images_matched,
            shapes_added=summary.shapes_added,
            classes_created=summary.classes_created,
            splits_set=summary.splits_set,
            unmatched_images=summary.unmatched_images,
            notes=[{"subject": n.subject, "reason": n.reason} for n in summary.notes[:200]],
        )
    if problem is not None:
        return DatasetOutcome("failed", reason=problem)
    return DatasetOutcome("none")


class ProjectView:
    """Streams a project's images and shapes to a format writer, a chunk at a time."""

    def __init__(
        self,
        session: Session,
        project_id: uuid.UUID,
        ctx: StorageContext,
        statuses: list[str] | None = None,
        splits: dict[uuid.UUID, str] | None = None,
        with_text: bool = False,
    ) -> None:
        self._splits = splits or {}
        self._with_text = with_text
        self._session = session
        self._project_id = project_id
        self._ctx = ctx
        self._statuses = statuses
        rows = session.execute(
            select(Class.id, Class.name)
            .where(Class.project_id == project_id)
            .order_by(Class.position)
        ).all()
        self._names = {cid: name for cid, name in rows}
        self.class_names = list(self._names.values())
        self.skeletons: dict[str, SkeletonSpec] = {}
        for name, skeleton in session.execute(
            select(Class.name, Class.skeleton).where(
                Class.project_id == project_id, Class.skeleton.is_not(None)
            )
        ):
            if skeleton:
                edges = [(int(a), int(b)) for a, b in skeleton["edges"]]
                self.skeletons[name] = SkeletonSpec(list(skeleton["names"]), edges)

    def images(self) -> Iterator[ExportImage]:
        stmt = select(Image).where(Image.project_id == self._project_id)
        if self._statuses:
            stmt = stmt.where(Image.status.in_(self._statuses))
        last = -1
        while True:
            chunk = list(
                self._session.scalars(
                    stmt.where(Image.position > last).order_by(Image.position).limit(CHUNK)
                )
            )
            if not chunk:
                return
            last = chunk[-1].position
            by_image: dict[uuid.UUID, list[Shape]] = {i.id: [] for i in chunk}
            rows = self._session.scalars(
                select(Annotation)
                .where(Annotation.image_id.in_(list(by_image)))
                .order_by(Annotation.created_at)
            )
            for ann in rows:
                if ann.class_id in self._names:
                    by_image[ann.image_id].append(
                        Shape(self._names[ann.class_id], ann.type, ann.geometry, ann.attrs)
                    )
                elif ann.class_id is None and ann.type == "text" and self._with_text:
                    by_image[ann.image_id].append(Shape("", ann.type, ann.geometry))
            for img in chunk:
                try:
                    source: Path | None = image_path(img, self._ctx)
                except (NotFound, OSError):  # a missing original only means it is not copied
                    source = None
                yield ExportImage(
                    img.filename,
                    img.width,
                    img.height,
                    by_image[img.id],
                    source,
                    self._splits.get(img.id),
                )


def count_export(session: Session, project_id: uuid.UUID, statuses: list[str] | None) -> int:
    stmt = select(func.count(Image.id)).where(Image.project_id == project_id)
    if statuses:
        stmt = stmt.where(Image.status.in_(statuses))
    return session.scalar(stmt) or 0


def _class_order(session: Session, project_id: uuid.UUID) -> list[str]:
    ids = session.scalars(
        select(Class.id).where(Class.project_id == project_id).order_by(Class.position)
    )
    return [str(i) for i in ids]


def _assign_splits(
    session: Session, project_id: uuid.UUID, opts: ExportOptions, statuses: list[str] | None
) -> dict[uuid.UUID, str]:
    """The split for each exported image: a fresh one when asked for, else the saved one."""
    spec = opts.split
    if spec is not None:
        config = splits.SplitConfig(spec.ratios, spec.seed, spec.stratify)
        return splits.plan(session, project_id, config, statuses=statuses).assignments
    if not opts.use_saved_splits:
        return {}
    stmt = select(Image.id, Image.split).where(Image.project_id == project_id)
    if statuses:
        stmt = stmt.where(Image.status.in_(statuses))
    saved = {image_id: name for image_id, name in session.execute(stmt)}
    if not any(saved.values()):
        return {}
    # Images with no split yet go with the training images.
    return {image_id: name or "train" for image_id, name in saved.items()}


#: What a move did, so a failed export can put each picture back.
#: The tuple is (image, old storage key, old file, new file).
MovedPicture = tuple[Image, str, Path, Path]


def move_pictures(
    session: Session,
    project_id: uuid.UUID,
    ctx: StorageContext,
    destination: Path,
    statuses: list[str] | None,
) -> list[MovedPicture]:
    """Move the pictures in an export's scope into `destination/images`.

    Covers both kinds: pictures connected from a folder, which leave that folder, and pictures
    uploaded into Katib, which leave its data folder. The project then reads them from their new
    place, and the new folder is remembered as one of its folders so that survives a restart.
    """
    rows = list(
        session.scalars(
            select(Image).where(Image.project_id == project_id).order_by(Image.position)
        )
    )
    if statuses:
        rows = [r for r in rows if r.status in statuses]
    images_dir = destination / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    moved: list[MovedPicture] = []
    try:
        for image in rows:
            source = image_path(image, ctx)
            target = images_dir / source.name
            if target.exists():
                target = images_dir / f"{image.id.hex[:8]}-{source.name}"
            shutil.move(str(source), str(target))
            moved.append((image, image.storage_key, source, target))
            image.storage_key = FILE_PREFIX + str(target.resolve())
    except BaseException:
        restore_pictures(moved)
        raise
    if moved:
        allow_folder(ctx, images_dir.resolve())
        known = session.scalar(
            select(ProjectFolder).where(
                ProjectFolder.project_id == project_id,
                ProjectFolder.path == str(images_dir.resolve()),
            )
        )
        if known is None:
            session.add(ProjectFolder(project_id=project_id, path=str(images_dir.resolve())))
    return moved


def restore_pictures(moved: list[MovedPicture]) -> None:
    """Undo `move_pictures`: each file goes back to where it was, and the project reads it there."""
    for image, old_key, old_file, new_file in reversed(moved):
        if new_file.exists():
            shutil.move(str(new_file), str(old_file))
        image.storage_key = old_key


def export_info(session: Session, project_id: uuid.UUID) -> dict[str, object]:
    """Whether the class order differs from the last export, which changes YOLO indices."""
    project = session.get(Project, project_id)
    if project is None:
        raise NotFound("That project does not exist.")
    last = project.settings.get("last_export_order")
    changed = last is not None and last != _class_order(session, project_id)
    return {"order_changed": changed, "has_exported": last is not None}


def export_dataset(
    session: Session,
    project_id: uuid.UUID,
    format_id: str,
    dest: Path,
    ctx: StorageContext,
    opts: ExportOptions,
    statuses: list[str] | None = None,
) -> ExportReport:
    try:
        fmt = get_format(format_id)
    except FormatError as err:
        raise InvalidInput(str(err)) from err
    splits = _assign_splits(session, project_id, opts, statuses)
    view = ProjectView(session, project_id, ctx, statuses, splits, "text" in fmt.supports)
    if not view.class_names and "text" not in fmt.supports:
        raise InvalidInput("Add at least one class before exporting.")
    report = fmt.write(view, dest, opts)
    del report.notes[MAX_NOTES:]
    project = session.get(Project, project_id)
    if project is not None:
        project.settings = {
            **project.settings,
            "last_export_order": _class_order(session, project_id),
        }
        session.flush()
    return report
