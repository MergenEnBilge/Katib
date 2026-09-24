from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from katib.api import app as app_module
from katib.api.app import create_app
from katib.config import Settings


@pytest.fixture
def ui_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>katib ui</html>")
    (static / "assets" / "app.js").write_text("console.log(1)")
    secret = tmp_path / "secret.txt"
    secret.write_text("do not serve")
    monkeypatch.setattr(app_module, "STATIC_DIR", static)
    settings = Settings(storage={"data_dir": str(tmp_path / "data")})
    with TestClient(create_app(settings)) as c:
        yield c


def test_serves_index_at_root(ui_client: TestClient) -> None:
    res = ui_client.get("/")
    assert res.status_code == 200
    assert "katib ui" in res.text


def test_serves_built_assets(ui_client: TestClient) -> None:
    res = ui_client.get("/assets/app.js")
    assert res.text == "console.log(1)"


def test_unknown_route_falls_back_to_index(ui_client: TestClient) -> None:
    assert "katib ui" in ui_client.get("/projects/abc").text


@pytest.mark.parametrize(
    "path", ["/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"]
)
def test_paths_cannot_escape_the_static_dir(ui_client: TestClient, path: str) -> None:
    res = ui_client.get(path)
    assert "do not serve" not in res.text


def test_api_paths_are_never_answered_by_the_ui(ui_client: TestClient) -> None:
    assert ui_client.get("/api/v1/nope").status_code == 404
