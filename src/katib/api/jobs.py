"""Job routes."""

import uuid

from fastapi import APIRouter

from katib.api.deps import RunnerDep
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
def get_job(job_id: uuid.UUID, runner: RunnerDep) -> JobOut:
    job = runner.get(job_id)
    if job is None:
        raise NotFound("That job does not exist.")
    return job_out(job)
