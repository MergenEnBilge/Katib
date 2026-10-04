"""Request and response models."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ProjectIn(BaseModel):
    name: str
    annotation_types: (
        list[Literal["box", "polygon", "obb", "keypoints", "mask", "tag", "text"]] | None
    ) = None


class ProjectPatch(BaseModel):
    name: str | None = None
    review_enabled: bool | None = None


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    annotation_types: list[str]
    review_enabled: bool = False
    role: str = "owner"
    image_count: int
    done_count: int
    created_at: datetime
    last_edited: datetime | None
    cover_image_id: uuid.UUID | None = None


class ClassIn(BaseModel):
    name: str
    color: str | None = None


class AttrDef(BaseModel):
    name: str
    type: Literal["boolean", "enum", "text", "number"]
    options: list[str] | None = None


class Skeleton(BaseModel):
    """Landmark names in drawing order, and pairs of positions that are joined by a line."""

    names: list[str] = Field(max_length=128)
    edges: list[tuple[int, int]] = Field(default_factory=list[tuple[int, int]])


class ClassPatch(BaseModel):
    name: str | None = None
    color: str | None = None
    attr_schema: list[AttrDef] | None = None
    # An empty list of names removes the skeleton.
    skeleton: Skeleton | None = None


class ClassOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    color: str
    position: int
    annotation_count: int
    attr_schema: list[AttrDef]
    skeleton: Skeleton | None = None


class ReorderIn(BaseModel):
    class_ids: list[uuid.UUID]


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    width: int
    height: int
    status: str
    split: str | None = None
    position: int
    version: int
    annotation_count: int = 0
    assignee_id: uuid.UUID | None = None
    reviewer_id: uuid.UUID | None = None
    lock: "LockOut | None" = None


class LockOut(BaseModel):
    user_id: uuid.UUID
    name: str | None
    until: datetime
    mine: bool = False


ImageOut.model_rebuild()


class ImagePageOut(BaseModel):
    items: list[ImageOut]
    next: uuid.UUID | None


class ImagePatch(BaseModel):
    status: Literal["todo", "in_progress", "done", "approved", "rejected"]


class FolderImportIn(BaseModel):
    folder: str


class PlaceOut(BaseModel):
    name: str
    path: str


class FolderListingOut(BaseModel):
    path: str | None
    parent: str | None
    places: list[PlaceOut]
    folders: list[PlaceOut]
    images_here: int
    can_connect: bool
    #: Katib is in a container, so only folders mounted at startup are reachable from here.
    in_container: bool = False
    label_files: list[PlaceOut] = []


class HaveIn(BaseModel):
    #: SHA-256 digests of pictures a browser is about to send.
    hashes: list[str] = Field(max_length=5000)


class HaveOut(BaseModel):
    #: The digests this project already holds, so the browser can skip sending those pictures.
    have: list[str]


class ConnectFolderIn(BaseModel):
    path: str


class ConnectedFolderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    path: str
    created_at: datetime
    #: A copy uploaded from another device into Katib's own data folder, not a folder read in
    #: place. Rescanning one finds nothing new: nothing else ever writes there.
    copied: bool = False


class ForgotMissingOut(BaseModel):
    removed: int


class JobOut(BaseModel):
    id: uuid.UUID
    kind: str
    status: str
    progress: float
    result: dict[str, Any] | None
    error: str | None


class ShareOut(BaseModel):
    reachable: bool
    accounts: bool
    urls: list[str]
    secure: bool
    app_url: str = ""
    #: Katib is in a container, so it cannot work out the address of the machine hosting it.
    in_container: bool = False
    #: Katib is open to the network but does not know which address to hand out. Ask for one.
    needs_address: bool = False
    #: The port Katib is listening on, to suggest when asking for the address.
    port: int = 0


class MlModelOut(BaseModel):
    name: str
    classes: list[str] | None


class ModelDownloadOut(BaseModel):
    id: str
    label: str
    help: str
    bytes: int
    installed: bool


class MlStatusOut(BaseModel):
    """Whether pre-labeling can run, and what is needed if it cannot."""

    enabled: bool
    installed: bool
    models_dir: str
    models: list[MlModelOut]
    #: A Segment Anything model is loaded, so clicking an object can outline it.
    can_segment: bool = False
    downloads: list[ModelDownloadOut] = []


class PrelabelIn(BaseModel):
    model: str
    threshold: float = 0.25
    only_unlabeled: bool = True
    create_missing_classes: bool = True
    # For models that do not carry their class names. One name per class, in the model's order.
    class_names: list[str] | None = None


class ClickIn(BaseModel):
    """A click on a picture, as a fraction of its width and height."""

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    #: False for "not this": a click that pushes the outline back off something it swallowed.
    positive: bool = True


class SegmentIn(BaseModel):
    points: list[ClickIn] = Field(max_length=32)


class SegmentOut(BaseModel):
    #: The outline as x, y pairs between 0 and 1. Empty when the model found nothing there.
    points: list[list[float]]


class ConnectResultOut(BaseModel):
    folder: ConnectedFolderOut
    job: JobOut


class UploadFileOut(BaseModel):
    #: False for a file that was neither a picture nor one of the label files read alongside
    #: them. Not an error -- a folder picker sweeps up plenty of those.
    kept: bool


class AnnotationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    image_id: uuid.UUID
    class_id: uuid.UUID | None
    type: str
    geometry: dict[str, Any]
    attrs: dict[str, Any]
    source: str
    confidence: float | None
    version: int


class OpIn(BaseModel):
    op: Literal["create", "update", "delete"]
    id: uuid.UUID
    type: str | None = None
    class_id: uuid.UUID | None = None
    geometry: dict[str, Any] | None = None
    attrs: dict[str, Any] | None = None
    if_version: int | None = None
    patch: dict[str, Any] = Field(default_factory=dict)


class BatchIn(BaseModel):
    ops: list[OpIn]


class OpResultOut(BaseModel):
    id: uuid.UUID
    status: Literal["ok", "conflict", "not_found", "invalid"]
    annotation: AnnotationOut | None = None
    error: str | None = None


class BatchOut(BaseModel):
    results: list[OpResultOut]


class FormatOut(BaseModel):
    id: str
    label: str
    supports: list[str]
    #: Some formats Katib only reads, such as segmentation masks saved as pictures.
    can_export: bool = True


class DatasetImportIn(BaseModel):
    path: str
    format: str | None = None


class SplitIn(BaseModel):
    train: float = 0.8
    val: float = 0.1
    test: float = 0.1
    seed: int = 0
    stratify: bool = False


class ExportIn(BaseModel):
    format: str
    split: SplitIn | None = None
    use_saved_splits: bool = True
    statuses: list[Literal["todo", "in_progress", "done"]] | None = None
    copy_images: bool = False
    #: A folder on the Katib computer to write the export into, instead of a zip to download.
    #: Only administrators can choose one, and it must be empty or not exist yet.
    destination: str | None = Field(default=None, max_length=1024)
    #: Move the pictures into the destination instead of copying them. Pictures leave their folder
    #: and the label files refer to them by name. Needs confirm_move, so it is never by accident.
    move_originals: bool = False
    confirm_move: bool = False
