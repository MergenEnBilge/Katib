"""Import and export of whole datasets through format plugins.

Formats work on plain dataclasses. This module maps them to and from the database: matching
images by filename, resolving class names and aliases, and streaming a project out.
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from katib.core.dataset import ExportImage, ExportOptions, ExportReport, Note, Shape
from katib.core.split import SplitError, SplitItem, assign_splits
from katib.core.types import GeometryError, validate_geometry
from katib.db.ids import new_id
from katib.db.models import Annotation, Class, Image, Project
from katib.formats import FormatError, detect_format, get_format
from katib.services import classes
from katib.services.errors import InvalidInput, NotFound
from katib.services.images import StorageContext, image_path

CHUNK = 200
MAX_NOTES = 200


@dataclass
class ImportSummary:
    format_id: str
    images_matched: int = 0
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
    try:
        fmt = get_format(format_id) if format_id else detect_format(path)
        parsed = fmt.read(path)
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

    by_name: dict[str, Image] = {}
    by_stem: dict[str, list[Image]] = {}
    for img in session.scalars(select(Image).where(Image.project_id == project_id)):
        by_name[img.filename.lower()] = img
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
        image = by_name.get(key)
        if image is None:
            candidates = by_stem.get(Path(key).stem, [])
            if len(candidates) == 1:
                image = candidates[0]
            elif len(candidates) > 1:
                summary.notes.append(Note(labels.filename, "More than one image has this name."))
        if image is None:
            summary.unmatched_images += 1
            continue
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
                    class_id=class_ids[shape.class_name],
                    type=shape.type,
                    geometry=geometry,
                    source="import",
                )
            )
            summary.shapes_added += 1
    session.flush()
    del summary.notes[MAX_NOTES:]
    return summary


class ProjectView:
    """Streams a project's images and shapes to a format writer, a chunk at a time."""

    def __init__(
        self,
        session: Session,
        project_id: uuid.UUID,
        ctx: StorageContext,
        statuses: list[str] | None = None,
        splits: dict[uuid.UUID, str] | None = None,
    ) -> None:
        self._splits = splits or {}
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
                        Shape(self._names[ann.class_id], ann.type, ann.geometry)
                    )
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
    spec = opts.split
    if spec is None:
        return {}
    stmt = select(Image.id).where(Image.project_id == project_id)
    if statuses:
        stmt = stmt.where(Image.status.in_(statuses))
    ids = list(session.scalars(stmt))
    classes_by_image: dict[uuid.UUID, set[str]] = {i: set() for i in ids}
    if spec.stratify:
        rows = session.execute(
            select(Annotation.image_id, Annotation.class_id)
            .where(Annotation.image_id.in_(ids), Annotation.class_id.is_not(None))
            .distinct()
        )
        for image_id, class_id in rows:
            classes_by_image[image_id].add(str(class_id))
    items = [SplitItem(str(i), frozenset(c)) for i, c in classes_by_image.items()]
    try:
        chosen = assign_splits(items, spec.ratios, spec.seed, spec.stratify)
    except SplitError as err:
        raise InvalidInput(str(err)) from err
    return {uuid.UUID(k): v for k, v in chosen.items()}


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
    view = ProjectView(session, project_id, ctx, statuses, splits)
    if not view.class_names:
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
