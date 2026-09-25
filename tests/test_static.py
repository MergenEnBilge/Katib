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


def test_hashed_assets_are_cached_for_a_year_and_the_page_is_always_checked(
    ui_client: TestClient,
) -> None:
    assert "immutable" in ui_client.get("/assets/app.js").headers["cache-control"]
    assert ui_client.get("/").headers["cache-control"] == "no-cache"


def test_big_text_files_are_sent_compressed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html></html>")
    (static / "assets" / "big.js").write_bytes(b"const answer = 42;\n" * 500)
    (static / "assets" / "tiny.js").write_text("1")
    monkeypatch.setattr(app_module, "STATIC_DIR", static)
    with TestClient(create_app(Settings(storage={"data_dir": str(tmp_path / "d")}))) as c:
        big = c.get("/assets/big.js", headers={"accept-encoding": "gzip"})
        assert big.headers["content-encoding"] == "gzip"
        assert big.headers["content-type"].startswith(("text/javascript", "application/javascript"))
        assert big.text == "const answer = 42;\n" * 500  # the client unpacks it
        plain = c.get("/assets/big.js", headers={"accept-encoding": "identity"})
        assert "content-encoding" not in plain.headers
        assert (
            "content-encoding"
            not in c.get("/assets/tiny.js", headers={"accept-encoding": "gzip"}).headers
        )


def test_the_apis_json_is_compressed_but_pictures_are_not(client: TestClient) -> None:
    for n in range(40):
        client.post("/api/v1/projects", json={"name": f"A project with a fairly long name {n}"})
    listing = client.get("/api/v1/projects", headers={"accept-encoding": "gzip"})
    assert listing.headers["content-encoding"] == "gzip"
    assert len(listing.json()) == 40
