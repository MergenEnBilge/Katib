"""Routes for the buckets a server reads pictures from."""

import uuid

from fastapi import APIRouter, Response

from katib.api.app_settings import AdminDep
from katib.api.deps import RunnerDep, SessionDep, StorageDep, UserDep, need
from katib.api.jobs import job_out
from katib.api.schemas import (
    CloudImportIn,
    CloudNameOut,
    CloudSourceIn,
    CloudSourceOut,
    CloudTestOut,
    JobOut,
)
from katib.jobs.runner import Progress
from katib.services import cloud_sources, projects
from katib.services.errors import NotFound
from katib.storage.cloud import Source

router = APIRouter(tags=["cloud"])


def _out(source: Source) -> CloudSourceOut:
    """Everything but the key. A secret that has been saved is never sent back out."""
    return CloudSourceOut(
        name=source.name,
        provider=source.provider,
        bucket=source.bucket,
        region=source.region,
        endpoint=source.endpoint,
        prefix=source.prefix,
        access_key=source.access_key,
    )


@router.get("/settings/cloud", response_model=list[CloudSourceOut])
def list_sources(_admin: AdminDep, storage: StorageDep) -> list[CloudSourceOut]:
    """The buckets set up on this server."""
    return [_out(s) for s in cloud_sources.load(storage.data_dir)]


@router.get("/cloud-sources", response_model=list[CloudNameOut])
def list_names(user: UserDep, storage: StorageDep) -> list[CloudNameOut]:
    """The names of the buckets, for choosing one when importing. Anyone signed in may look."""
    return [
        CloudNameOut(name=s.name, provider=s.provider) for s in cloud_sources.load(storage.data_dir)
    ]


@router.put("/settings/cloud", response_model=CloudTestOut)
def save_source(body: CloudSourceIn, _admin: AdminDep, storage: StorageDep) -> CloudTestOut:
    """Add a bucket, or replace one of the same name. The details are tried before they are kept."""
    found = cloud_sources.put(
        storage.data_dir,
        Source(
            name=body.name,
            provider=body.provider,
            bucket=body.bucket,
            access_key=body.access_key,
            secret=body.secret,
            region=body.region,
            endpoint=body.endpoint,
            prefix=body.prefix,
        ),
    )
    return CloudTestOut(objects=found)


@router.delete("/settings/cloud/{name}", status_code=204, response_class=Response)
def forget_source(name: str, _admin: AdminDep, storage: StorageDep) -> Response:
    """Forget a bucket. Pictures already in a project cannot be opened until it is set up again."""
    cloud_sources.remove(storage.data_dir, name)
    return Response(status_code=204)


@router.post("/projects/{project_id}/cloud-imports", response_model=JobOut, status_code=202)
def import_from_cloud(
    project_id: uuid.UUID,
    body: CloudImportIn,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    runner: RunnerDep,
) -> JobOut:
    """Bring the pictures under a name in the bucket into this project, without copying them in."""
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    # Fail now, while the person is waiting, rather than inside the job.
    cloud_sources.get(storage.data_dir, body.source)
    factory = runner.session_factory
    data_dir = storage.data_dir

    def work(progress: Progress) -> dict[str, object]:
        with factory() as s:
            report = cloud_sources.import_prefix(
                s, project_id, body.source, body.prefix, storage, data_dir, progress
            )
        return {
            "added": report.added,
            "skipped": [{"name": k.name, "reason": k.reason} for k in report.skipped[:200]],
            "skipped_count": len(report.skipped),
        }

    job_id = runner.submit("import_cloud", project_id, {"source": body.source}, work)
    job = runner.get(job_id)
    if job is None:
        raise NotFound("The import could not be started.")
    return job_out(job)
