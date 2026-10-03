"""Folder routes: browse the Katib computer and connect folders to projects."""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile

from katib.api.deps import AnywhereDep, RunnerDep, SessionDep, StorageDep, UserDep, need
from katib.api.images import start_import
from katib.api.schemas import (
    ConnectedFolderOut,
    ConnectFolderIn,
    ConnectResultOut,
    FolderListingOut,
    ForgotMissingOut,
    JobOut,
    PlaceOut,
    UploadFileOut,
)
from katib.db.models import ProjectFolder
from katib.services import folders, images, projects
from katib.services.errors import InvalidInput
from katib.services.images import StorageContext

router = APIRouter(tags=["folders"])


def _out(folder: ProjectFolder, storage: StorageContext) -> ConnectedFolderOut:
    uploads = storage.folder_uploads.path("").resolve()
    where = Path(folder.path).resolve()
    return ConnectedFolderOut(
        id=folder.id,
        path=folder.path,
        created_at=folder.created_at,
        copied=where == uploads or uploads in where.parents,
    )


@router.get("/folders", response_model=FolderListingOut)
def browse(
    user: UserDep, storage: StorageDep, anywhere: AnywhereDep, path: str | None = None
) -> FolderListingOut:
    """List the folders inside `path`, or the places to start from when no path is given."""
    listing = folders.browse(storage, path, unrestricted=anywhere)
    return FolderListingOut(
        path=listing.path,
        parent=listing.parent,
        places=[PlaceOut(name=p.name, path=p.path) for p in listing.places],
        folders=[PlaceOut(name=p.name, path=p.path) for p in listing.folders],
        images_here=listing.images_here,
        can_connect=listing.can_connect,
        in_container=listing.in_container,
        label_files=[PlaceOut(name=p.name, path=p.path) for p in listing.label_files],
    )


@router.get("/projects/{project_id}/folders", response_model=list[ConnectedFolderOut])
def list_connected(
    project_id: uuid.UUID, session: SessionDep, user: UserDep, storage: StorageDep
) -> list[ConnectedFolderOut]:
    need(session, user, project_id, "view")
    return [_out(f, storage) for f in folders.list_connected(session, project_id)]


@router.post("/projects/{project_id}/folders", response_model=ConnectResultOut, status_code=201)
def connect(
    project_id: uuid.UUID,
    body: ConnectFolderIn,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    runner: RunnerDep,
    anywhere: AnywhereDep,
) -> ConnectResultOut:
    """Remember a folder for the project and start reading its images."""
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    folder = folders.connect(session, project_id, body.path, storage, unrestricted=anywhere)
    # The job writes from its own connection, so the folder row must be committed first.
    session.commit()
    job = start_import(runner, storage, project_id, folder.path)
    return ConnectResultOut(folder=_out(folder, storage), job=job)


@router.post("/projects/{project_id}/folders:upload-file", response_model=UploadFileOut)
def upload_folder_file(
    project_id: uuid.UUID,
    batch: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
) -> UploadFileOut:
    """Save one file of a folder chosen in the browser. Call once per file, then :upload-finish.

    This is the way in when Katib cannot browse the computer it runs on -- most often because it
    is in a container, where the filesystem the browser sees and the one Katib sees are not the
    same thing. The browser can still see the real folder, so it sends what is in it instead of a
    path Katib would have no way to reach. One request per file, rather than the whole folder in
    one, is what lets the person watch it happen instead of staring at a spinner.
    """
    need(session, user, project_id, "manage")
    kept = images.keep_uploaded_folder_file(
        storage, project_id, batch, file.filename or "", file.file
    )
    return UploadFileOut(kept=kept)


@router.post(
    "/projects/{project_id}/folders:upload-finish", response_model=ConnectResultOut, status_code=201
)
def upload_folder_finish(
    project_id: uuid.UUID,
    batch: Annotated[uuid.UUID, Form()],
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    runner: RunnerDep,
) -> ConnectResultOut:
    """Connect the folder a set of :upload-file calls just built and start reading it."""
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    root = images.upload_batch_path(storage, project_id, batch)
    if not root.is_dir() or images.count_uploaded_folder_files(storage, project_id, batch) == 0:
        raise InvalidInput(
            "None of those files could be used. Choose a folder with pictures in it."
        )

    folder = folders.connect(session, project_id, str(root), storage, unrestricted=True)
    # The job writes from its own connection, so the folder row must be committed first.
    session.commit()
    job = start_import(runner, storage, project_id, folder.path)
    return ConnectResultOut(folder=_out(folder, storage), job=job)


@router.post(
    "/projects/{project_id}/folders/{folder_id}:rescan", response_model=JobOut, status_code=202
)
def rescan(
    project_id: uuid.UUID,
    folder_id: uuid.UUID,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    runner: RunnerDep,
) -> JobOut:
    """Pick up images that were added to a connected folder since the last scan."""
    need(session, user, project_id, "manage")
    folder = folders.get_connected(session, project_id, folder_id)
    return start_import(runner, storage, project_id, folder.path)


@router.post(
    "/projects/{project_id}/folders/{folder_id}:forget-missing", response_model=ForgotMissingOut
)
def forget_missing(
    project_id: uuid.UUID,
    folder_id: uuid.UUID,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
) -> ForgotMissingOut:
    """Take pictures whose files have left this folder out of the project, shapes and all."""
    need(session, user, project_id, "manage")
    folder = folders.get_connected(session, project_id, folder_id)
    gone = images.missing_in_folder(session, project_id, folder.path)
    return ForgotMissingOut(removed=images.forget_images(session, storage, gone))


@router.delete("/projects/{project_id}/folders/{folder_id}", status_code=204)
def disconnect(
    project_id: uuid.UUID, folder_id: uuid.UUID, session: SessionDep, user: UserDep
) -> Response:
    need(session, user, project_id, "manage")
    folders.disconnect(session, folders.get_connected(session, project_id, folder_id))
    return Response(status_code=204)
