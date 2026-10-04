"""Text documents end to end: adding them, labelling spans, exporting and reading back."""

import json
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from katib.api.app import create_app
from katib.config import Settings

API = "/api/v1"
REVIEW = "Katib runs on my laptop. The canvas is quick."


@pytest.fixture
def api(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(storage={"data_dir": str(tmp_path / "data")})
    with TestClient(create_app(settings)) as c:
        yield c


def text_project(api: TestClient, name: str = "Reviews") -> str:
    made = api.post(
        f"{API}/projects", json={"name": name, "annotation_types": ["span", "tag", "text"]}
    )
    assert made.status_code == 201, made.text
    return made.json()["id"]


def wait(api: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(400):
        job = api.get(f"{API}/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError("the job did not finish")


def add_file(api: TestClient, project: str, name: str, body: str) -> dict[str, Any]:
    res = api.post(
        f"{API}/projects/{project}/documents",
        files={"file": (name, body.encode("utf-8"), "text/plain")},
    )
    assert res.status_code == 202, res.text
    job = wait(api, res.json()["id"])
    assert job["status"] == "done", job
    return job["result"]


def items(api: TestClient, project: str) -> list[dict[str, Any]]:
    return api.get(f"{API}/projects/{project}/images", params={"limit": 200}).json()["items"]


def test_a_text_file_becomes_a_document_whose_words_can_be_read(api: TestClient) -> None:
    project = text_project(api)
    result = add_file(api, project, "review.txt", REVIEW)
    assert result["added"] == 1 and result["skipped_count"] == 0

    [document] = items(api, project)
    assert document["kind"] == "text"
    assert document["filename"] == "review.txt"
    # A document keeps its length where a picture keeps its width, so counting works for both.
    assert document["width"] == len(REVIEW)

    words = api.get(f"{API}/images/{document['id']}/text")
    assert words.status_code == 200
    assert words.json() == {"filename": "review.txt", "text": REVIEW}


def test_the_same_words_twice_are_added_once(api: TestClient) -> None:
    project = text_project(api)
    add_file(api, project, "one.txt", REVIEW)
    again = add_file(api, project, "two.txt", REVIEW)
    assert again["added"] == 0
    assert "already in one.txt" in again["skipped"][0]["reason"]
    assert len(items(api, project)) == 1


def test_a_span_is_saved_and_cannot_reach_past_the_words(api: TestClient) -> None:
    project = text_project(api)
    add_file(api, project, "review.txt", REVIEW)
    [document] = items(api, project)
    product = api.post(f"{API}/projects/{project}/classes", json={"name": "product"}).json()

    good = str(uuid.uuid4())
    res = api.post(
        f"{API}/images/{document['id']}/annotations:batch",
        json={
            "ops": [
                {
                    "op": "create",
                    "id": good,
                    "type": "span",
                    "class_id": product["id"],
                    "geometry": {"start": 0, "end": 5},
                },
                {
                    "op": "create",
                    "id": str(uuid.uuid4()),
                    "type": "span",
                    "class_id": product["id"],
                    "geometry": {"start": 0, "end": len(REVIEW) + 10},
                },
                {
                    "op": "create",
                    "id": str(uuid.uuid4()),
                    "type": "span",
                    "class_id": product["id"],
                    "geometry": {"start": 7, "end": 7},
                },
            ]
        },
    )
    assert res.status_code == 200, res.text
    states = [r["status"] for r in res.json()["results"]]
    assert states == ["ok", "invalid", "invalid"]
    reasons = " ".join(r.get("error") or "" for r in res.json()["results"])
    assert "past the end" in reasons and "end after it starts" in reasons

    saved = api.get(f"{API}/images/{document['id']}/annotations").json()
    assert [(s["type"], s["geometry"]) for s in saved] == [("span", {"start": 0, "end": 5})]


def test_a_picture_shape_is_refused_on_a_document(api: TestClient) -> None:
    project = api.post(
        f"{API}/projects", json={"name": "Mixed", "annotation_types": ["span", "box"]}
    ).json()["id"]
    add_file(api, project, "review.txt", REVIEW)
    [document] = items(api, project)
    car = api.post(f"{API}/projects/{project}/classes", json={"name": "car"}).json()
    res = api.post(
        f"{API}/images/{document['id']}/annotations:batch",
        json={
            "ops": [
                {
                    "op": "create",
                    "id": str(uuid.uuid4()),
                    "type": "box",
                    "class_id": car["id"],
                    "geometry": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
                }
            ]
        },
    )
    assert res.json()["results"][0]["status"] == "invalid"
    assert "cannot hold a box" in res.json()["results"][0]["error"]


def test_a_jsonl_file_brings_its_documents_spans_and_classes(api: TestClient) -> None:
    project = text_project(api)
    lines = [
        json.dumps(
            {
                "id": "first",
                "text": "Katib runs here.",
                "spans": [{"start": 0, "end": 5, "label": "product"}],
            }
        ),
        # The spaCy and Prodigy shape: a list of [start, end, label].
        json.dumps({"id": "second", "text": "Paris in spring.", "entities": [[0, 5, "place"]]}),
        json.dumps({"id": "third", "text": "No labels on this one."}),
        "not json at all",
        json.dumps({"id": "fourth", "no": "text"}),
    ]
    result = add_file(api, project, "reviews.jsonl", "\n".join(lines))
    assert result["added"] == 3
    assert result["spans"] == 2
    assert sorted(result["classes_created"]) == ["place", "product"]
    assert result["skipped_count"] == 2

    by_name = {i["filename"]: i for i in items(api, project)}
    assert sorted(by_name) == ["first", "second", "third"]
    spans = api.get(f"{API}/images/{by_name['first']['id']}/annotations").json()
    assert spans[0]["geometry"] == {"start": 0, "end": 5}


def test_spans_export_and_come_back_in(api: TestClient, tmp_path: Path) -> None:
    project = text_project(api)
    add_file(
        api,
        project,
        "reviews.jsonl",
        json.dumps(
            {
                "id": "first",
                "text": REVIEW,
                "spans": [{"start": 0, "end": 5, "label": "product"}],
                "tags": ["positive"],
            }
        ),
    )
    destination = tmp_path / "spans-export"
    started = api.post(
        f"{API}/projects/{project}/exports",
        json={"format": "jsonl-spans", "destination": str(destination)},
    )
    assert started.status_code == 202, started.text
    job = wait(api, started.json()["id"])
    assert job["status"] == "done", job
    assert job["result"]["images"] == 1 and job["result"]["shapes"] == 2

    written = (destination / "documents.jsonl").read_text(encoding="utf-8").strip()
    row = json.loads(written)
    assert row["text"] == REVIEW
    assert row["spans"] == [{"start": 0, "end": 5, "label": "product", "text": "Katib"}]
    assert row["tags"] == ["positive"]

    # The same file read back into a fresh project with the same documents.
    second = text_project(api, "Reviews again")
    add_file(api, second, "first.txt", REVIEW)
    read = api.post(f"{API}/projects/{second}/imports", json={"path": str(destination)})
    assert read.status_code == 202, read.text
    back = wait(api, read.json()["id"])
    assert back["status"] == "done", back
    assert back["result"]["format"] == "jsonl-spans"
    assert back["result"]["shapes_added"] == 2

    [document] = items(api, second)
    kinds = sorted(s["type"] for s in api.get(f"{API}/images/{document['id']}/annotations").json())
    assert kinds == ["span", "tag"]


def test_a_file_katib_cannot_read_says_so(api: TestClient) -> None:
    project = text_project(api)
    wrong = api.post(
        f"{API}/projects/{project}/documents",
        files={"file": ("photo.png", b"\x89PNG\r\n", "image/png")},
    )
    assert wrong.status_code == 422
    assert ".jsonl" in wrong.json()["message"]

    binary = api.post(
        f"{API}/projects/{project}/documents",
        files={"file": ("notes.txt", b"\xff\xfe\x00bad", "text/plain")},
    )
    assert binary.status_code == 422
    assert "UTF-8" in binary.json()["message"]
