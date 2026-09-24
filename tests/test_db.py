import time
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from katib.db.ids import new_id
from katib.db.migrate import upgrade_to_head
from katib.db.models import Class, Project
from katib.db.session import make_engine, make_session_factory, session_scope


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    upgrade_to_head(url)
    return url


def test_migration_creates_all_tables(db_url: str) -> None:
    tables = set(inspect(make_engine(db_url)).get_table_names())
    expected = {
        "users", "projects", "project_members", "images", "classes", "class_aliases",
        "annotations", "comments", "operations", "activity", "jobs", "api_tokens",
    }  # fmt: skip
    assert expected <= tables


def test_class_names_are_unique_per_project_ignoring_case(db_url: str) -> None:
    factory = make_session_factory(make_engine(db_url))
    with session_scope(factory) as s:
        p = Project(name="P", slug="p")
        s.add(p)
        s.flush()
        s.add(Class(project_id=p.id, name="Car", color="#4C8DF6", position=0))
        project_id = p.id

    with pytest.raises(IntegrityError), session_scope(factory) as s:
        s.add(Class(project_id=project_id, name="car", color="#8B6CF0", position=1))


def test_foreign_keys_are_enforced(db_url: str) -> None:
    engine = make_engine(db_url)
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_new_ids_are_v7_and_unique() -> None:
    ids = [new_id() for _ in range(200)]
    assert all(i.version == 7 for i in ids)
    assert len(set(ids)) == 200


def test_new_ids_sort_by_creation_time() -> None:
    first = new_id()
    time.sleep(0.003)
    assert first < new_id()
