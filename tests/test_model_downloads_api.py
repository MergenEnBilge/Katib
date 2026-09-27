"""The model download endpoints, with the actual network fetch stubbed out.

The download service itself is exercised against a real local server in test_model_downloads.py.
Here the point is the API around it: who may start one, what the catalog looks like before and
after, and that a finished download is reflected in /ml.
"""

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from katib.api.app import create_app
from katib.config import Settings
from katib.ml import sam
from katib.services import model_downloads

API = "/api/v1"


@pytest.fixture
def api(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        storage={"data_dir": str(tmp_path / "data")},
        ml={"enabled": True, "models_dir": str(tmp_path / "models")},
    )
    with TestClient(create_app(settings)) as client:
        yield client


def wait_job(api: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(300):
        job: dict[str, Any] = api.get(f"{API}/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_the_catalog_is_listed_and_starts_uninstalled(api: TestClient) -> None:
    downloads = api.get(f"{API}/ml").json()["downloads"]
    assert {d["id"] for d in downloads} == {m.id for m in model_downloads.CATALOG}
    assert all(not d["installed"] for d in downloads)
    assert all(d["bytes"] > 0 and d["label"] and d["help"] for d in downloads)


def test_an_unknown_model_id_is_refused(api: TestClient) -> None:
    reply = api.post(f"{API}/ml/models:download", data={"model_id": "not-a-model"})
    assert reply.status_code == 422


def test_a_finished_download_shows_up_as_installed(
    api: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = model_downloads.CATALOG[0]

    def fake_install(source: Any, folder: Path, progress: Any = None) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / sam.ENCODER_NAME).write_bytes(b"encoder")
        (folder / sam.DECODER_NAME).write_bytes(b"decoder")
        (folder / model_downloads.MARKER_NAME).write_text(source.id)

    monkeypatch.setattr(model_downloads, "download_and_install", fake_install)

    started = api.post(f"{API}/ml/models:download", data={"model_id": entry.id}).json()
    done = wait_job(api, started["id"])
    assert done["status"] == "done", done

    status = api.get(f"{API}/ml").json()
    downloaded = next(d for d in status["downloads"] if d["id"] == entry.id)
    assert downloaded["installed"] is True
    assert status["can_segment"] is True


def test_only_an_administrator_can_download_a_model_on_a_shared_server(tmp_path: Path) -> None:
    settings = Settings(
        storage={"data_dir": str(tmp_path / "data")},
        auth={"mode": "local"},
        ml={"enabled": True, "models_dir": str(tmp_path / "models")},
    )
    with TestClient(create_app(settings)) as api:
        api.post(
            "/api/v1/auth/setup",
            json={"email": "a@x.org", "name": "Admin", "password": "correct horse battery"},
        )
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
            entry = model_downloads.CATALOG[0]
            reply = other.post(f"{API}/ml/models:download", data={"model_id": entry.id})
            assert reply.status_code == 403
