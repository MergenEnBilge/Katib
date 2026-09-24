from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from katib.api.app import create_app
from katib.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(storage={"data_dir": str(tmp_path)})


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c
