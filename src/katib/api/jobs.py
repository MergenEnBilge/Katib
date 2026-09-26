"""Job routes."""

import uuid

from fastapi import APIRouter

from katib.api.deps import AnywhereDep, RunnerDep, SessionDep, UserDep, need
from katib.api.schemas import JobOut
from katib.db.models import Job
from katib.services.errors import NotFound

router = APIRouter(tags=["jobs"])


def job_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        kind=job.kind,
        status=job.status,
        progress=job.progress,
        result=job.result,
        error=job.error,
    )


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: uuid.UUID,
    runner: RunnerDep,
    session: SessionDep,
    user: UserDep,
    anywhere: AnywhereDep,
) -> JobOut:
    job = runner.get(job_id)
    if job is None:
        raise NotFound("That job does not exist.")
    if job.project_id is not None:
        need(session, user, job.project_id, "view")
    elif not anywhere:
        # The only jobs with no project are backups, which are an administrator's business. Their
        # progress and the name of the file they wrote are not for everybody.
        raise NotFound("That job does not exist.")
    return job_out(job)
