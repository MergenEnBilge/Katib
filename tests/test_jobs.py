import time
from pathlib import Path
from typing import Any

import pytest

from katib.db.migrate import upgrade_to_head
from katib.db.models import Job
from katib.db.session import make_engine, make_session_factory
from katib.jobs.runner import JobRunner, Progress


@pytest.fixture
def runner(tmp_path: Path):  # type: ignore[no-untyped-def]
    url = f"sqlite:///{(tmp_path / 'jobs.db').as_posix()}"
    upgrade_to_head(url)
    engine = make_engine(url)
    r = JobRunner(make_session_factory(engine))
    yield r
    r.shutdown()
    engine.dispose()


def wait_for(runner: JobRunner, job_id: Any) -> Job:
    for _ in range(200):
        job = runner.get(job_id)
        assert job is not None
        if job.status in ("done", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_job_runs_and_stores_result(runner: JobRunner) -> None:
    def work(progress: Progress) -> dict[str, Any]:
        progress(0.5)
        return {"added": 3}

    job = wait_for(runner, runner.submit("import_images", None, {}, work))
    assert job.status == "done"
    assert job.progress == 1.0
    assert job.result == {"added": 3}
    assert job.finished_at is not None


def test_failed_job_records_error(runner: JobRunner) -> None:
    def work(progress: Progress) -> dict[str, Any]:
        raise RuntimeError("disk is full")

    job = wait_for(runner, runner.submit("export", None, {}, work))
    assert job.status == "failed"
    assert job.error == "disk is full"


def test_interrupted_jobs_are_failed_on_startup(runner: JobRunner) -> None:
    factory = runner._factory  # noqa: SLF001
    with factory() as s:
        s.add(Job(kind="export", status="running"))
        s.add(Job(kind="export", status="done"))
        s.commit()
    assert runner.fail_interrupted() == 1
    with factory() as s:
        statuses = sorted(j.status for j in s.query(Job))
    assert statuses == ["done", "failed"]
