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


class Team:
    def __init__(self, admin: TestClient, library: Path) -> None:
        self.admin = admin
        project = admin.post(f"{API}/projects", json={"name": "Shared"}).json()
        self.pid: str = project["id"]
        job = admin.post(
            f"{API}/projects/{self.pid}/images:import-folder", json={"folder": str(library)}
        ).json()
        for _ in range(300):
            if admin.get(f"{API}/jobs/{job['id']}").json()["status"] == "done":
                break
            time.sleep(0.02)
        self.images: list[dict[str, Any]] = admin.get(f"{API}/projects/{self.pid}/images").json()[
            "items"
        ]
        self.people: dict[str, TestClient] = {}
        self.ids: dict[str, str] = {}
        for name, role in [("ann1", "annotator"), ("ann2", "annotator"), ("rev", "reviewer")]:
            self.people[name] = self.join(name, role)

    def join(self, name: str, role: str) -> TestClient:
        token = self.admin.post(
            f"{API}/invites", json={"project_id": self.pid, "role": role}
        ).json()["token"]
        client = TestClient(self.admin.app)
        res = client.post(
            f"{API}/auth/accept",
            json={
                "token": token,
                "email": f"{name}@example.com",
                "name": name,
                "password": PASSWORD,
            },
        )
        assert res.status_code == 201, res.text
        self.ids[name] = res.json()["id"]
        return client


@pytest.fixture
def team(tmp_path: Path) -> Iterator[Team]:
    lib = tmp_path / "lib"
    lib.mkdir()
    for i in range(4):
        PILImage.new("RGB", (30 + i, 20), (i * 40, 10, 10)).save(lib / f"img{i}.png")
    settings = Settings(
        storage={"data_dir": str(tmp_path / "data"), "allowed_import_roots": [str(lib)]},
        auth={"mode": "local"},
    )
    with TestClient(create_app(settings)) as admin:
        admin.post(
            f"{API}/auth/setup",
            json={"email": "admin@example.com", "name": "Admin", "password": PASSWORD},
        )
        yield Team(admin, lib)


def test_next_gives_each_person_their_own_image(team: Team) -> None:
    a = team.people["ann1"].post(f"{API}/projects/{team.pid}/next").json()["image"]
    b = team.people["ann2"].post(f"{API}/projects/{team.pid}/next").json()["image"]
    again = team.people["ann1"].post(f"{API}/projects/{team.pid}/next").json()["image"]
    assert a["id"] != b["id"] and again["id"] == a["id"]
    assert a["status"] == "in_progress" and a["assignee_id"] == team.ids["ann1"]
    viewer_token = team.admin.post(
        f"{API}/invites", json={"project_id": team.pid, "role": "viewer"}
    ).json()["token"]
    viewer = TestClient(team.admin.app)
    viewer.post(
        f"{API}/auth/accept",
        json={"token": viewer_token, "email": "v@example.com", "name": "V", "password": PASSWORD},
    )
    assert viewer.post(f"{API}/projects/{team.pid}/next").status_code == 403


def test_soft_locks_over_http(team: Team) -> None:
    image = team.images[0]["id"]
    ann1, ann2 = team.people["ann1"], team.people["ann2"]
    mine = ann1.post(f"{API}/images/{image}/lock")
    assert mine.status_code == 200 and mine.json()["mine"] is True
    assert ann1.post(f"{API}/images/{image}/lock").status_code == 200

    held = ann2.post(f"{API}/images/{image}/lock")
    assert held.status_code == 409 and held.json()["code"] == "image_locked"
    assert held.json()["details"]["name"] == "ann1"
    listed = ann2.get(f"{API}/projects/{team.pid}/images").json()["items"][0]
    assert listed["lock"]["name"] == "ann1" and listed["lock"]["mine"] is False

    assert ann2.post(f"{API}/images/{image}/lock:take-over").status_code == 403
    taken = team.admin.post(f"{API}/images/{image}/lock:take-over")
    assert taken.status_code == 200 and taken.json()["name"] == "Admin"
    assert ann1.delete(f"{API}/images/{image}/lock").status_code == 204
    assert ann2.post(f"{API}/images/{image}/lock").status_code == 409
    assert team.admin.delete(f"{API}/images/{image}/lock").status_code == 204
    assert ann2.post(f"{API}/images/{image}/lock").status_code == 200


def test_review_flow_comments_activity_and_inbox(team: Team) -> None:
    ann, rev = team.people["ann1"], team.people["rev"]
    image = ann.post(f"{API}/projects/{team.pid}/next").json()["image"]["id"]
    review_off = rev.patch(f"{API}/images/{image}", json={"status": "approved"})
    assert review_off.status_code == 422 and "Review is off" in review_off.json()["message"]

    assert rev.patch(f"{API}/projects/{team.pid}", json={"review_enabled": True}).status_code == 403
    on = team.admin.patch(f"{API}/projects/{team.pid}", json={"review_enabled": True}).json()
    assert on["review_enabled"] is True and on["role"] == "owner"

    assert ann.patch(f"{API}/images/{image}", json={"status": "done"}).json()["status"] == "done"
    queue = rev.get(f"{API}/inbox").json()
    assert [i["image_id"] for i in queue["to_review"]] == [image]
    assert ann.get(f"{API}/inbox").json()["to_review"] == []

    comment = rev.post(
        f"{API}/images/{image}/comments", json={"body": "Box is too loose", "x": 0.3, "y": 0.4}
    )
    assert comment.status_code == 201 and comment.json()["author"] == "rev"
    assert rev.patch(f"{API}/images/{image}", json={"status": "rejected"}).json()["reviewer_id"]

    inbox = ann.get(f"{API}/inbox").json()
    assert [(i["image_id"], i["status"]) for i in inbox["assigned"]] == [(image, "rejected")]
    seen = ann.get(f"{API}/images/{image}/comments").json()
    assert [c["body"] for c in seen] == ["Box is too loose"]
    resolved = ann.post(f"{API}/comments/{seen[0]['id']}:resolve", json={"resolved": True}).json()
    assert resolved["resolved"] is True

    assert ann.patch(f"{API}/images/{image}", json={"status": "done"}).status_code == 200
    assert (
        rev.patch(f"{API}/images/{image}", json={"status": "approved"}).json()["status"]
        == "approved"
    )
    assert ann.patch(f"{API}/images/{image}", json={"status": "in_progress"}).status_code == 403

    feed = ann.get(f"{API}/projects/{team.pid}/activity").json()
    verbs = [f["verb"] for f in feed]
    assert "marked_approved" in verbs and "commented" in verbs and "marked_rejected" in verbs
    assert feed[0]["who"] == "rev"


def test_assignment_by_a_manager(team: Team) -> None:
    ids = [i["id"] for i in team.images[:2]]
    body = {"image_ids": ids, "assignee_id": team.ids["ann2"]}
    assert (
        team.people["ann1"].post(f"{API}/projects/{team.pid}/images:assign", json=body).status_code
        == 403
    )
    assigned = team.admin.post(f"{API}/projects/{team.pid}/images:assign", json=body)
    assert assigned.json() == {"assigned": 2}
    first = team.people["ann2"].post(f"{API}/projects/{team.pid}/next").json()["image"]
    assert first["id"] == ids[0]
    other = team.people["ann1"].post(f"{API}/projects/{team.pid}/next").json()["image"]
    assert other["id"] not in ids
