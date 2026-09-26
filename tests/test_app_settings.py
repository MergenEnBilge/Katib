import io
import json
import time
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage

from katib.api.app import create_app
from katib.config import DEFAULT_DATABASE_URL, Settings, read_saved

API = "/api/v1"


@pytest.fixture
def library(tmp_path: Path) -> Path:
    folder = tmp_path / "photos"
    folder.mkdir()
    return folder


@pytest.fixture
def api(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(storage={"data_dir": str(tmp_path / "data")}))) as c:
        yield c


def field(payload: dict[str, Any], key: str) -> dict[str, Any]:
    return next(f for f in payload["fields"] if f["key"] == key)


def test_every_setting_is_listed_with_help_and_a_value(api: TestClient, sqlite_only: None) -> None:
    got = api.get(f"{API}/settings").json()
    keys = {f["key"] for f in got["fields"]}
    assert {"auth.mode", "server.port", "limits.max_upload_mb", "ml.enabled"} <= keys
    assert all(f["help"] and f["label"] for f in got["fields"])
    assert got["info"]["database"] == "SQLite"
    assert {g["id"] for g in got["groups"]} >= {"sharing", "storage", "limits", "model"}


def test_a_limit_changes_at_once_and_is_saved(api: TestClient, tmp_path: Path) -> None:
    got = api.put(f"{API}/settings", json={"values": {"limits.max_upload_mb": 3}}).json()
    assert field(got, "limits.max_upload_mb")["value"] == 3
    assert field(got, "limits.max_upload_mb")["source"] == "saved"
    assert not got["info"]["restart_pending"]
    assert read_saved(tmp_path / "data")["limits"]["max_upload_mb"] == 3

    big = io.BytesIO(b"x" * (4 * 1024 * 1024))
    project = api.post(f"{API}/projects", json={"name": "P"}).json()
    upload = api.post(
        f"{API}/projects/{project['id']}/images", files={"file": ("big.png", big, "image/png")}
    )
    assert upload.status_code == 422
    assert "3 MB" in upload.json()["message"]


def test_a_setting_that_needs_a_restart_says_so(api: TestClient) -> None:
    got = api.put(f"{API}/settings", json={"values": {"server.port": 9123}}).json()
    port = field(got, "server.port")
    assert port["restart_pending"] is True
    assert port["value"] == 9123
    assert port["running"] == 8420
    assert got["info"]["restart_pending"] is True


def test_the_folders_katib_may_read_take_effect_at_once(api: TestClient, library: Path) -> None:
    body = {"values": {"storage.allowed_import_roots": [str(library)]}}
    got = api.put(f"{API}/settings", json=body).json()
    assert field(got, "storage.allowed_import_roots")["value"] == [str(library)]
    listing = api.get(f"{API}/folders", params={"path": str(library)})
    assert listing.status_code == 200


@pytest.mark.parametrize(
    ("values", "words"),
    [
        ({"limits.max_upload_mb": 0}, "between"),
        ({"limits.max_upload_mb": "lots"}, "whole number"),
        ({"server.port": 70000}, "between"),
        ({"server.public_url": "ftp://katib.example.com"}, "address"),
        ({"storage.allowed_import_roots": ["/no/such/place"]}, "not a folder"),
        ({"ml.enabled": "yes"}, "on or off"),
        ({"nothing.here": 1}, "not a setting"),
        ({"server.host": "0.0.0.0"}, "loopback"),
    ],
)
def test_bad_values_are_refused_with_a_reason(
    api: TestClient, values: dict[str, Any], words: str
) -> None:
    reply = api.put(f"{API}/settings", json={"values": values})
    assert reply.status_code == 422
    assert words in reply.json()["message"]


def test_the_public_address_may_be_typed_the_way_it_is_typed_in_a_browser(api: TestClient) -> None:
    """Nobody types a scheme into a browser, so Katib should not insist on one here."""
    reply = api.put(f"{API}/settings", json={"values": {"server.public_url": "192.168.1.20:8420"}})
    assert reply.status_code == 200
    saved = [f for f in reply.json()["fields"] if f["key"] == "server.public_url"][0]
    assert saved["value"] == "http://192.168.1.20:8420"


def test_sharing_on_the_network_works_once_accounts_are_chosen_too(api: TestClient) -> None:
    both = {"auth.mode": "local", "server.host": "0.0.0.0"}
    assert api.put(f"{API}/settings", json={"values": both}).status_code == 200


def test_the_database_offers_the_built_in_one_as_a_choice(api: TestClient) -> None:
    """Most people should never have to think about a connection string."""
    got = api.get(f"{API}/settings").json()
    database = field(got, "database.url")
    assert database["kind"] == "choice"
    assert database["allow_other"] is True
    assert [o["value"] for o in database["options"]] == [DEFAULT_DATABASE_URL]


def test_an_address_that_is_not_a_database_is_still_refused(
    api: TestClient, sqlite_only: None
) -> None:
    refused = api.put(f"{API}/settings", json={"values": {"database.url": "my database"}})
    assert refused.status_code == 422
    assert "sqlite:///" in refused.json()["message"]


def test_the_database_password_is_never_shown(api: TestClient, sqlite_only: None) -> None:
    url = "postgresql://katib:hunter2@db.example.com:5432/katib"
    got = api.put(f"{API}/settings", json={"values": {"database.url": url}}).json()
    shown = field(got, "database.url")["value"]
    assert "hunter2" not in shown
    assert "****" in shown
    # Sending the masked text back does not overwrite the real one.
    again = api.put(f"{API}/settings", json={"values": {"database.url": shown}}).json()
    assert field(again, "database.url")["value"] == shown
    assert "hunter2" not in json.dumps(again)


def test_environment_settings_are_locked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KATIB_LIMITS__MAX_UPLOAD_MB", "9")
    settings = Settings(storage={"data_dir": str(tmp_path / "data")})
    with TestClient(create_app(settings)) as api:
        locked = field(api.get(f"{API}/settings").json(), "limits.max_upload_mb")
        assert locked["source"] == "environment"
        assert locked["env_name"] == "KATIB_LIMITS__MAX_UPLOAD_MB"
        reply = api.put(f"{API}/settings", json={"values": {"limits.max_upload_mb": 5}})
        assert reply.status_code == 422
        assert "environment" in reply.json()["message"]


def test_only_administrators_change_settings_on_a_shared_server(tmp_path: Path) -> None:
    settings = Settings(storage={"data_dir": str(tmp_path / "data")}, auth={"mode": "local"})
    with TestClient(create_app(settings)) as api:
        assert api.get(f"{API}/settings").status_code == 401
        api.post(
            f"{API}/auth/setup",
            json={"email": "a@x.org", "name": "Admin", "password": "correct horse battery"},
        )
        assert api.get(f"{API}/settings").status_code == 200
        invite = api.post(f"{API}/invites", json={"project_id": None, "role": "viewer"}).json()
        with TestClient(api.app) as other:
            other.post(
                f"{API}/auth/accept",
                json={
                    "token": invite["token"],
                    "email": "b@x.org",
                    "name": "Bea",
                    "password": "correct horse battery",
                },
            )
            assert other.get(f"{API}/settings").status_code == 403
            assert other.put(f"{API}/settings", json={"values": {}}).status_code == 403
            assert other.post(f"{API}/settings/backup").status_code == 403


def wait_job(api: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(300):
        job: dict[str, Any] = api.get(f"{API}/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_a_backup_holds_the_database_and_uploads(api: TestClient, sqlite_only: None) -> None:
    project = api.post(f"{API}/projects", json={"name": "Kept"}).json()
    buffer = io.BytesIO()
    PILImage.new("RGB", (8, 8), "red").save(buffer, "PNG")
    buffer.seek(0)
    api.post(
        f"{API}/projects/{project['id']}/images", files={"file": ("a.png", buffer, "image/png")}
    )
    job = api.post(f"{API}/settings/backup").json()
    done = wait_job(api, job["id"])
    assert done["status"] == "done", done
    blob = api.get(f"{API}/jobs/{job['id']}/download").content
    names = zipfile.ZipFile(io.BytesIO(blob)).namelist()
    assert "katib.db" in names
    assert "backup.json" in names
    assert any(n.startswith("uploads/") for n in names)
