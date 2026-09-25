import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage

from katib.api.app import create_app
from katib.config import Settings

API = "/api/v1"
PASSWORD = "correct horse battery"


def photo(path: Path, color: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    PILImage.new("RGB", (16, 16), color).save(path)


def wait_job(api: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(300):
        job = api.get(f"{API}/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


@pytest.fixture
def library(tmp_path: Path) -> Path:
    lib = tmp_path / "library"
    photo(lib / "a.png", "red")
    photo(lib / "trips" / "b.png", "blue")
    (lib / ".hidden").mkdir()
    return lib


@pytest.fixture
def solo(tmp_path: Path) -> Iterator[TestClient]:
    """One person on their own computer: no folders configured, no accounts."""
    with TestClient(create_app(Settings(storage={"data_dir": str(tmp_path / "data")}))) as c:
        yield c


def new_project(api: TestClient) -> str:
    return str(api.post(f"{API}/projects", json={"name": "Photos"}).json()["id"])


def test_browse_starts_from_places_and_lists_subfolders(solo: TestClient, library: Path) -> None:
    start = solo.get(f"{API}/folders").json()
    assert start["path"] is None
    assert start["places"][0]["name"] == "Home"

    listing = solo.get(f"{API}/folders", params={"path": str(library)}).json()
    assert [f["name"] for f in listing["folders"]] == ["trips"]
    assert listing["images_here"] == 1
    assert listing["parent"] == str(library.parent.resolve())
    assert listing["can_connect"] is True


def test_connect_reads_images_and_remembers_the_folder(solo: TestClient, library: Path) -> None:
    project = new_project(solo)
    res = solo.post(f"{API}/projects/{project}/folders", json={"path": str(library)})
    assert res.status_code == 201, res.text
    assert wait_job(solo, res.json()["job"]["id"])["result"]["added"] == 2

    saved = solo.get(f"{API}/projects/{project}/folders").json()
    assert [f["path"] for f in saved] == [str(library.resolve())]

    again = solo.post(f"{API}/projects/{project}/folders", json={"path": str(library)})
    assert again.json()["folder"]["id"] == saved[0]["id"]


def test_rescan_adds_only_new_images(solo: TestClient, library: Path) -> None:
    project = new_project(solo)
    first = solo.post(f"{API}/projects/{project}/folders", json={"path": str(library)}).json()
    wait_job(solo, first["job"]["id"])

    photo(library / "c.png", "green")
    res = solo.post(f"{API}/projects/{project}/folders/{first['folder']['id']}:rescan")
    assert res.status_code == 202
    job = wait_job(solo, res.json()["id"])

    assert job["result"]["added"] == 1
    assert job["result"]["skipped_count"] == 0
    assert solo.get(f"{API}/projects/{project}").json()["image_count"] == 3


def test_disconnect_keeps_the_images(solo: TestClient, library: Path) -> None:
    project = new_project(solo)
    made = solo.post(f"{API}/projects/{project}/folders", json={"path": str(library)}).json()
    wait_job(solo, made["job"]["id"])

    assert (
        solo.delete(f"{API}/projects/{project}/folders/{made['folder']['id']}").status_code == 204
    )
    assert solo.get(f"{API}/projects/{project}/folders").json() == []
    assert solo.get(f"{API}/projects/{project}").json()["image_count"] == 2


def test_a_missing_folder_is_a_clear_error(solo: TestClient, tmp_path: Path) -> None:
    project = new_project(solo)
    res = solo.post(f"{API}/projects/{project}/folders", json={"path": str(tmp_path / "nope")})
    assert res.status_code == 422
    assert res.json()["message"] == "That folder does not exist."


def test_connected_folders_survive_a_restart(tmp_path: Path, library: Path) -> None:
    settings = Settings(storage={"data_dir": str(tmp_path / "data")})
    with TestClient(create_app(settings)) as first:
        project = new_project(first)
        made = first.post(f"{API}/projects/{project}/folders", json={"path": str(library)}).json()
        wait_job(first, made["job"]["id"])

    with TestClient(create_app(settings)) as second:
        images = second.get(f"{API}/projects/{project}/images").json()["items"]
        assert second.get(f"{API}/images/{images[0]['id']}/file").status_code == 200


def test_on_a_shared_server_only_the_administrator_connects_new_folders(
    tmp_path: Path, library: Path
) -> None:
    settings = Settings(storage={"data_dir": str(tmp_path / "data")}, auth={"mode": "local"})
    with TestClient(create_app(settings)) as admin:
        admin.post(
            f"{API}/auth/setup",
            json={"email": "admin@example.com", "name": "Admin", "password": PASSWORD},
        )
        project = new_project(admin)
        invite = admin.post(f"{API}/invites", json={"project_id": project, "role": "manager"})
        manager = TestClient(admin.app)
        manager.post(
            f"{API}/auth/accept",
            json={
                "token": invite.json()["token"],
                "email": "m@example.com",
                "name": "Manager",
                "password": PASSWORD,
            },
        )

        assert manager.get(f"{API}/folders").json()["places"] == []
        denied = manager.post(f"{API}/projects/{project}/folders", json={"path": str(library)})
        assert denied.status_code == 403

        assert (
            admin.post(f"{API}/projects/{project}/folders", json={"path": str(library)}).status_code
            == 201
        )
        inside = manager.get(f"{API}/folders", params={"path": str(library)})
        assert inside.status_code == 200
        assert inside.json()["parent"] is None
        assert manager.get(f"{API}/folders", params={"path": str(tmp_path)}).status_code == 403


def test_folder_names_become_splits(tmp_path: Path) -> None:
    lib = tmp_path / "dataset"
    photo(lib / "images" / "train" / "a.png", "red")
    photo(lib / "images" / "val" / "b.png", "blue")
    photo(lib / "images" / "other" / "c.png", "green")
    with TestClient(
        create_app(
            Settings(
                storage={"data_dir": str(tmp_path / "data"), "allowed_import_roots": [str(lib)]}
            )
        )
    ) as api:
        pid = new_project(api)
        job = api.post(
            f"{API}/projects/{pid}/images:import-folder", json={"folder": str(lib)}
        ).json()
        assert wait_job(api, job["id"])["status"] == "done"
        items = api.get(f"{API}/projects/{pid}/images").json()["items"]
    assert {i["filename"]: i["split"] for i in items} == {
        "a.png": "train",
        "b.png": "val",
        "c.png": None,
    }
