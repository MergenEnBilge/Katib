from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from katib.api.app import create_app
from katib.config import Settings
from katib.db.migrate import upgrade_to_head
from katib.db.session import make_engine, make_session_factory


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(storage={"data_dir": str(tmp_path)})


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    """A session on a freshly migrated SQLite database."""
    url = f"sqlite:///{(tmp_path / 'svc.db').as_posix()}"
    upgrade_to_head(url)
    engine = make_engine(url)
    with make_session_factory(engine)() as s:
        yield s
    engine.dispose()
