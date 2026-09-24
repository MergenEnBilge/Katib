"""In-process job runner. Job state lives in the `jobs` table so it survives a page reload.

Work runs on a small thread pool. Progress is written to the row (throttled) so clients can poll
it. Jobs left `running` by a previous process are marked failed on startup.
"""

import logging
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast

from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, sessionmaker

from katib.db.base import utcnow
from katib.db.models import Job

log = logging.getLogger(__name__)

Progress = Callable[[float], None]
Work = Callable[[Progress], dict[str, Any]]

WRITE_INTERVAL = 0.4


class JobRunner:
    def __init__(self, factory: sessionmaker[Session], workers: int = 2) -> None:
        self._factory = factory
        self.session_factory = factory
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="katib-job")

    def fail_interrupted(self) -> int:
        """Mark jobs a previous process left unfinished as failed, with a message to retry."""
        with self._factory() as s:
            result = cast(
                "CursorResult[Any]",
                s.execute(
                    update(Job)
                    .where(Job.status.in_(("queued", "running")))
                    .values(
                        status="failed",
                        error="Katib stopped before this finished. Start it again.",
                        finished_at=utcnow(),
                    )
                ),
            )
            s.commit()
            return result.rowcount or 0

    def submit(
        self, kind: str, project_id: uuid.UUID | None, params: dict[str, Any], work: Work
    ) -> uuid.UUID:
        with self._factory() as s:
            job = Job(kind=kind, project_id=project_id, params=params)
            s.add(job)
            s.commit()
            job_id = job.id
        self._pool.submit(self._run, job_id, work)
        return job_id

    def get(self, job_id: uuid.UUID) -> Job | None:
        with self._factory() as s:
            return s.get(Job, job_id)

    def _set(self, job_id: uuid.UUID, **values: Any) -> None:
        with self._factory() as s:
            s.execute(update(Job).where(Job.id == job_id).values(**values))
            s.commit()

    def _run(self, job_id: uuid.UUID, work: Work) -> None:
        self._set(job_id, status="running")
        last = 0.0

        def progress(fraction: float) -> None:
            nonlocal last
            now = time.monotonic()
            if fraction >= 1.0 or now - last >= WRITE_INTERVAL:
                last = now
                self._set(job_id, progress=min(1.0, max(0.0, fraction)))

        try:
            result = work(progress)
        except Exception as err:  # noqa: BLE001 - a job failing must never take the worker down
            log.exception("Job %s failed", job_id)
            self._set(job_id, status="failed", error=str(err), finished_at=utcnow())
        else:
            self._set(job_id, status="done", progress=1.0, result=result, finished_at=utcnow())

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
