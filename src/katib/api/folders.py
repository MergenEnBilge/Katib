"""Folder routes: browse the Katib computer and connect folders to projects."""

import uuid

from fastapi import APIRouter, Response

from katib.api.deps import AnywhereDep, RunnerDep, SessionDep, StorageDep, UserDep, need
from katib.api.images import start_import
from katib.api.schemas import (
    ConnectedFolderOut,
    ConnectFolderIn,
    ConnectResultOut,
    FolderListingOut,
    JobOut,
    PlaceOut,
)
from katib.services import folders, projects

router = APIRouter(tags=["folders"])


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
    )


@router.get("/projects/{project_id}/folders", response_model=list[ConnectedFolderOut])
def list_connected(
    project_id: uuid.UUID, session: SessionDep, user: UserDep
) -> list[ConnectedFolderOut]:
    need(session, user, project_id, "view")
    return [
        ConnectedFolderOut.model_validate(f) for f in folders.list_connected(session, project_id)
    ]


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
    return ConnectResultOut(folder=ConnectedFolderOut.model_validate(folder), job=job)


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


@router.delete("/projects/{project_id}/folders/{folder_id}", status_code=204)
def disconnect(
    project_id: uuid.UUID, folder_id: uuid.UUID, session: SessionDep, user: UserDep
) -> Response:
    need(session, user, project_id, "manage")
    folders.disconnect(session, folders.get_connected(session, project_id, folder_id))
    return Response(status_code=204)
