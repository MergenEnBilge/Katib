"""Routes for class merge and delete, bulk edits, the operations history and revert."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from katib.api.deps import SessionDep, UserDep, need
from katib.api.hub import emit
from katib.db.models import Operation
from katib.services import access, class_ops, projects
from katib.services.errors import InvalidInput
from katib.storage.local import LocalStorage

router = APIRouter(tags=["class operations"])


def get_operations_storage(request: Request) -> LocalStorage:
    storage: LocalStorage = request.app.state.operations
    return storage


OpsStorage = Annotated[LocalStorage, Depends(get_operations_storage)]


class PreviewOut(BaseModel):
    annotations: int
    images: int
    dropped_attr_values: int


class OperationOut(BaseModel):
    id: uuid.UUID
    kind: str
    summary: str
    created_at: str
    reverted: bool
    can_revert: bool


class ClassOpOut(BaseModel):
    dry_run: bool
    preview: PreviewOut
    operation: OperationOut | None = None


class MergeIn(BaseModel):
    target_id: uuid.UUID
    dry_run: bool = False


class DeleteIn(BaseModel):
    dry_run: bool = False


class BulkIn(BaseModel):
    action: Literal["reclass", "delete"]
    ids: list[uuid.UUID]
    target_id: uuid.UUID | None = None
    dry_run: bool = False


class RevertOut(BaseModel):
    restored: int
    skipped: int
    message: str


def _preview(p: class_ops.Preview) -> PreviewOut:
    return PreviewOut(
        annotations=p.annotations, images=p.images, dropped_attr_values=p.dropped_attr_values
    )


def operation_out(op: Operation) -> OperationOut:
    return OperationOut(
        id=op.id,
        kind=op.kind,
        summary=op.summary,
        created_at=op.created_at.isoformat(),
        reverted=op.reverted_at is not None,
        can_revert=op.reverted_at is None and op.inverse_ref is not None,
    )


def _done(result: class_ops.OperationResult, session: Session | None = None) -> ClassOpOut:
    if session is not None:
        emit(session.info, result.operation.project_id, {"type": "class.changed"})
    return ClassOpOut(
        dry_run=False, preview=_preview(result.preview), operation=operation_out(result.operation)
    )


@router.post("/classes/{class_id}:merge", response_model=ClassOpOut)
def merge_class(
    class_id: uuid.UUID, body: MergeIn, session: SessionDep, user: UserDep, storage: OpsStorage
) -> ClassOpOut:
    need(session, user, access.project_of_class(session, class_id), "manage")
    if body.dry_run:
        preview = class_ops.preview_merge(session, class_id, body.target_id)
        return ClassOpOut(dry_run=True, preview=_preview(preview))
    return _done(class_ops.merge_classes(session, storage, class_id, body.target_id), session)


@router.post("/classes/{class_id}:delete", response_model=ClassOpOut)
def delete_class(
    class_id: uuid.UUID, body: DeleteIn, session: SessionDep, user: UserDep, storage: OpsStorage
) -> ClassOpOut:
    need(session, user, access.project_of_class(session, class_id), "manage")
    if body.dry_run:
        return ClassOpOut(
            dry_run=True, preview=_preview(class_ops.preview_delete(session, class_id))
        )
    return _done(class_ops.delete_class(session, storage, class_id), session)


@router.post("/projects/{project_id}/annotations:bulk", response_model=ClassOpOut)
def bulk_edit(
    project_id: uuid.UUID, body: BulkIn, session: SessionDep, user: UserDep, storage: OpsStorage
) -> ClassOpOut:
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    if body.action == "reclass" and body.target_id is None:
        raise InvalidInput("Choose the class to relabel them as.")
    if body.dry_run:
        return ClassOpOut(
            dry_run=True, preview=_preview(class_ops.preview_bulk(session, project_id, body.ids))
        )
    if body.action == "reclass" and body.target_id is not None:
        return _done(
            class_ops.bulk_reclass(session, storage, project_id, body.ids, body.target_id), session
        )
    return _done(class_ops.bulk_delete(session, storage, project_id, body.ids), session)


@router.get("/projects/{project_id}/operations", response_model=list[OperationOut])
def list_operations(
    project_id: uuid.UUID, session: SessionDep, user: UserDep
) -> list[OperationOut]:
    need(session, user, project_id, "view")
    projects.get_project(session, project_id)
    return [operation_out(o) for o in class_ops.list_operations(session, project_id)]


@router.post("/operations/{operation_id}:revert", response_model=RevertOut)
def revert_operation(
    operation_id: uuid.UUID, session: SessionDep, user: UserDep, storage: OpsStorage
) -> RevertOut:
    need(session, user, access.project_of_operation(session, operation_id), "manage")
    result = class_ops.revert(session, storage, operation_id)
    total = result.restored + result.skipped
    if result.skipped:
        message = (
            f"Restored {result.restored:,} of {total:,}. {result.skipped:,} were edited since."
        )
    else:
        message = f"Restored {result.restored:,}."
    return RevertOut(restored=result.restored, skipped=result.skipped, message=message)
