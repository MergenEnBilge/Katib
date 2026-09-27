import io
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage

from katib import net
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


def test_a_missing_folder_in_a_container_explains_the_mount(
    solo: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path that is simply wrong and one that was never mounted look identical from here, so
    the message has to cover the reason someone in Docker is actually going to hit."""
    monkeypatch.setattr(net, "in_container", lambda: True)
    project = new_project(solo)
    res = solo.post(f"{API}/projects/{project}/folders", json={"path": str(tmp_path / "nope")})
    assert res.status_code == 422
    assert "container" in res.json()["message"]
    assert "-v" in res.json()["message"]


def test_browsing_says_whether_katib_is_in_a_container(
    solo: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert solo.get(f"{API}/folders").json()["in_container"] is False
    monkeypatch.setattr(net, "in_container", lambda: True)
    assert solo.get(f"{API}/folders").json()["in_container"] is True


def test_no_allowed_folders_in_a_container_explains_the_mount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A shared server with nothing in storage.allowed_import_roots looks the same in Docker as
    on a bare machine, but only one of those is fixed by asking an administrator to add a path."""
    settings = Settings(storage={"data_dir": str(tmp_path / "data")}, auth={"mode": "local"})
    monkeypatch.setattr(net, "in_container", lambda: True)
    with TestClient(create_app(settings)) as api:
        api.post(
            f"{API}/auth/setup",
            json={"email": "a@example.com", "name": "A", "password": PASSWORD},
        )
        project = new_project(api)
        res = api.post(f"{API}/projects/{project}/images:import-folder", json={"folder": "/x"})
    assert res.status_code == 403
    assert "container" in res.json()["message"]


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


def png_bytes(size: tuple[int, int] = (16, 16), color: str = "red") -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def upload_file(
    api: TestClient, project: str, batch: str, name: str, content: bytes, content_type: str
) -> Any:
    return api.post(
        f"{API}/projects/{project}/folders:upload-file",
        data={"batch": batch},
        files={"file": (name, content, content_type)},
    )


def upload_finish(api: TestClient, project: str, batch: str) -> Any:
    return api.post(f"{API}/projects/{project}/folders:upload-finish", data={"batch": batch})


def test_uploading_a_folder_connects_it_like_a_browsed_one(solo: TestClient) -> None:
    """The way in when Katib cannot browse the computer it runs on: the browser sends what a
    folder picker saw, one file per request, and Katib treats the result like any connected
    folder once every file has arrived."""
    project = new_project(solo)
    batch = str(uuid.uuid4())
    for name, color in [("trip/a.png", "red"), ("trip/more/b.png", "blue")]:
        made = upload_file(solo, project, batch, name, png_bytes(color=color), "image/png")
        assert made.status_code == 200 and made.json()["kept"] is True, made.text

    finished = upload_finish(solo, project, batch)
    assert finished.status_code == 201, finished.text
    job = wait_job(solo, finished.json()["job"]["id"])
    assert job["status"] == "done", job
    assert job["result"]["added"] == 2
    assert len(solo.get(f"{API}/projects/{project}/images").json()["items"]) == 2
    assert len(solo.get(f"{API}/projects/{project}/folders").json()) == 1


def test_an_uploaded_folder_can_carry_its_labels_too(solo: TestClient) -> None:
    project = new_project(solo)
    batch = str(uuid.uuid4())
    yaml_text = "path: .\ntrain: images\nval: images\nnames:\n  0: car\n"
    upload_file(solo, project, batch, "set/data.yaml", yaml_text.encode(), "application/x-yaml")
    upload_file(solo, project, batch, "set/labels/a.txt", b"0 0.5 0.5 0.2 0.2\n", "text/plain")
    upload_file(solo, project, batch, "set/images/a.png", png_bytes(), "image/png")

    finished = upload_finish(solo, project, batch)
    assert finished.status_code == 201, finished.text
    job = wait_job(solo, finished.json()["job"]["id"])
    assert job["status"] == "done", job
    assert job["result"]["dataset"]["format"] == "yolo-detect"
    assert job["result"]["dataset"]["shapes_added"] == 1
    classes = {c["name"] for c in solo.get(f"{API}/projects/{project}/classes").json()}
    assert classes == {"car"}


def test_uploading_a_folder_ignores_files_it_cannot_use(solo: TestClient) -> None:
    """A folder picker sweeps up whatever is there. Only pictures and label files matter."""
    project = new_project(solo)
    batch = str(uuid.uuid4())
    kept = upload_file(solo, project, batch, "photos/a.png", png_bytes(), "image/png")
    assert kept.json()["kept"] is True
    for name in ("photos/.DS_Store", "photos/notes.docx"):
        ignored = upload_file(solo, project, batch, name, b"junk", "application/octet-stream")
        assert ignored.json()["kept"] is False

    finished = upload_finish(solo, project, batch)
    job = wait_job(solo, finished.json()["job"]["id"])
    assert job["result"]["added"] == 1


def test_uploading_a_folder_rejects_path_traversal_in_a_file_name(solo: TestClient) -> None:
    project = new_project(solo)
    batch = str(uuid.uuid4())
    kept = upload_file(solo, project, batch, "../../../etc/passwd.png", png_bytes(), "image/png")
    assert kept.status_code == 200 and kept.json()["kept"] is False

    finished = upload_finish(solo, project, batch)
    assert finished.status_code == 422
    assert "could be used" in finished.json()["message"]


def test_finishing_an_upload_nothing_was_sent_for_is_refused(solo: TestClient) -> None:
    project = new_project(solo)
    finished = upload_finish(solo, project, str(uuid.uuid4()))
    assert finished.status_code == 422


def test_a_folder_upload_is_capped(solo: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from katib.services import images as images_service

    monkeypatch.setattr(images_service, "MAX_FOLDER_UPLOAD_FILES", 1)
    project = new_project(solo)
    batch = str(uuid.uuid4())
    first = upload_file(solo, project, batch, "a.png", png_bytes(), "image/png")
    assert first.status_code == 200 and first.json()["kept"] is True
    second = upload_file(solo, project, batch, "b.png", png_bytes(color="blue"), "image/png")
    assert second.status_code == 422
    assert "limited to" in second.json()["message"]


def test_only_a_manager_can_upload_a_folder_on_a_shared_server(tmp_path: Path) -> None:
    settings = Settings(storage={"data_dir": str(tmp_path / "data")}, auth={"mode": "local"})
    with TestClient(create_app(settings)) as api:
        api.post(
            f"{API}/auth/setup",
            json={"email": "boss@example.com", "name": "Boss", "password": PASSWORD},
        )
        project = new_project(api)
        token = api.post(f"{API}/invites", json={"project_id": project, "role": "viewer"}).json()[
            "token"
        ]
        viewer = TestClient(api.app)
        viewer.post(
            f"{API}/auth/accept",
            json={"token": token, "email": "v@example.com", "name": "V", "password": PASSWORD},
        )
        refused = upload_file(viewer, project, str(uuid.uuid4()), "a.png", png_bytes(), "image/png")
    assert refused.status_code == 403
