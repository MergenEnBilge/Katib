"""Request dependencies: a transaction-scoped session and shared app services."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from katib.jobs.runner import JobRunner
from katib.services.images import StorageContext


def get_session(request: Request) -> Iterator[Session]:
    """One transaction per request: commit on success, roll back on any error."""
    session: Session = request.app.state.session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_storage(request: Request) -> StorageContext:
    ctx: StorageContext = request.app.state.storage
    return ctx


def get_runner(request: Request) -> JobRunner:
    runner: JobRunner = request.app.state.runner
    return runner


SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[StorageContext, Depends(get_storage)]
RunnerDep = Annotated[JobRunner, Depends(get_runner)]
