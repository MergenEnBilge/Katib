"""Shared fixtures. `--db postgres` runs the suite against a Postgres server.

Point it at a server with KATIB_TEST_POSTGRES_URL (default postgresql://postgres@127.0.0.1:5432/postgres).
Each test gets its own schema, which is dropped afterward, so tests stay isolated.
"""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from katib.api.app import create_app
from katib.config import Settings
from katib.db.migrate import upgrade_to_head
from katib.db.session import make_engine, make_session_factory, normalize_url

DEFAULT_PG = "postgresql://postgres@127.0.0.1:5432/postgres"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--db", action="store", default="sqlite", choices=["sqlite", "postgres"])


def is_postgres(config: pytest.Config) -> bool:
    return bool(config.getoption("--db") == "postgres")


@pytest.fixture
def database_url(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[str]:
    """A fresh, empty database URL for one test."""
    if not is_postgres(request.config):
        yield f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
        return
    base = normalize_url(os.environ.get("KATIB_TEST_POSTGRES_URL", DEFAULT_PG))
    schema = f"t_{uuid.uuid4().hex[:12]}"
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    joiner = "&" if "?" in base else "?"
    yield f"{base}{joiner}options=-csearch_path%3D{schema}"
    with admin.connect() as conn:
        conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin.dispose()


@pytest.fixture(autouse=True)
def _database_for_the_app(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """In Postgres mode every app the tests build uses the per-test schema."""
    if is_postgres(request.config):
        monkeypatch.setenv("KATIB_DATABASE__URL", request.getfixturevalue("database_url"))


@pytest.fixture
def sqlite_only(request: pytest.FixtureRequest) -> None:
    if is_postgres(request.config):
        pytest.skip("SQLite specific")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(storage={"data_dir": str(tmp_path)})


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def session(database_url: str) -> Iterator[Session]:
    """A session on a freshly migrated database."""
    upgrade_to_head(database_url)
    engine = make_engine(database_url)
    with make_session_factory(engine)() as s:
        yield s
    engine.dispose()
