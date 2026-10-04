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


def test_a_project_holds_pictures_or_text_but_not_both(api: TestClient) -> None:
    mixed = api.post(f"{API}/projects", json={"name": "Mixed", "annotation_types": ["span", "box"]})
    assert mixed.status_code == 422, mixed.text
    assert "cannot use box" in mixed.json()["message"]

    # Asking for a picture project and then a span is refused the same way round.
    wrong = api.post(
        f"{API}/projects",
        json={"name": "Pictures", "annotation_types": ["span"], "medium": "image"},
    )
    assert wrong.status_code == 422, wrong.text
    assert "cannot use span" in wrong.json()["message"]


def test_a_text_project_refuses_a_picture_shape(api: TestClient) -> None:
    project = text_project(api, "Words only")
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
    assert "does not use box" in res.json()["results"][0]["error"]


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


def test_a_file_written_on_windows_lines_up_with_its_spans(api: TestClient) -> None:
    """A carriage return on each line must not shift every span that follows it.

    The words are served with line endings settled, so the length Katib records has to be
    measured the same way. Otherwise a span drawn near the end of a long document is saved
    against offsets that no longer point at the words the person picked.
    """
    project = text_project(api)
    windows = "Katib runs here.\r\nThe canvas is quick.\r\nIt reads text too.\r\n"
    add_file(api, project, "windows.txt", windows)

    [document] = items(api, project)
    words = api.get(f"{API}/images/{document['id']}/text").json()["text"]
    assert "\r" not in words
    assert document["width"] == len(words)

    # The last word of the last line, counted in the text the browser is given.
    start = words.index("too")
    label = api.post(f"{API}/projects/{project}/classes", json={"name": "thing"}).json()
    res = api.post(
        f"{API}/images/{document['id']}/annotations:batch",
        json={
            "ops": [
                {
                    "op": "create",
                    "id": str(uuid.uuid4()),
                    "type": "span",
                    "class_id": label["id"],
                    "geometry": {"start": start, "end": start + 3},
                }
            ]
        },
    )
    assert res.json()["results"][0]["status"] == "ok", res.text
    saved = api.get(f"{API}/images/{document['id']}/annotations").json()
    geometry = saved[0]["geometry"]
    assert words[geometry["start"] : geometry["end"]] == "too"


def spans_on(api: TestClient, document: str, label: str, runs: list[tuple[int, int]]) -> list[str]:
    """Label some runs of characters and give back their ids."""
    ids = [str(uuid.uuid4()) for _ in runs]
    ops = [
        {
            "op": "create",
            "id": made,
            "type": "span",
            "class_id": label,
            "geometry": {"start": start, "end": end},
        }
        for made, (start, end) in zip(ids, runs, strict=True)
    ]
    res = api.post(f"{API}/images/{document}/annotations:batch", json={"ops": ops})
    assert [r["status"] for r in res.json()["results"]] == ["ok"] * len(runs), res.text
    return ids


def link(api: TestClient, document: str, label: str, start: str, end: str) -> dict[str, Any]:
    res = api.post(
        f"{API}/images/{document}/annotations:batch",
        json={
            "ops": [
                {
                    "op": "create",
                    "id": str(uuid.uuid4()),
                    "type": "relation",
                    "class_id": label,
                    "geometry": {"from_id": start, "to_id": end},
                }
            ]
        },
    )
    return dict(res.json()["results"][0])


def relation_project(api: TestClient, name: str = "Who works where") -> str:
    made = api.post(
        f"{API}/projects",
        json={"name": name, "annotation_types": ["span", "relation", "tag"]},
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def test_a_relation_joins_two_spans(api: TestClient) -> None:
    project = relation_project(api)
    add_file(api, project, "who.txt", "Ada works at Katib.")
    [document] = items(api, project)
    person = api.post(f"{API}/projects/{project}/classes", json={"name": "person"}).json()
    works = api.post(f"{API}/projects/{project}/classes", json={"name": "works for"}).json()
    ada, katib = spans_on(api, document["id"], person["id"], [(0, 3), (13, 18)])

    made = link(api, document["id"], works["id"], ada, katib)
    assert made["status"] == "ok", made

    saved = api.get(f"{API}/images/{document['id']}/annotations").json()
    [relation] = [s for s in saved if s["type"] == "relation"]
    assert relation["geometry"] == {"from_id": ada, "to_id": katib}


def test_a_relation_needs_two_different_spans_on_the_same_document(api: TestClient) -> None:
    project = relation_project(api, "Checks")
    add_file(api, project, "one.txt", "Ada works at Katib.")
    add_file(api, project, "two.txt", "Grace works at Katib too.")
    first, second = sorted(items(api, project), key=lambda i: i["filename"])
    person = api.post(f"{API}/projects/{project}/classes", json={"name": "person"}).json()
    works = api.post(f"{API}/projects/{project}/classes", json={"name": "works for"}).json()
    [ada] = spans_on(api, first["id"], person["id"], [(0, 3)])
    [grace] = spans_on(api, second["id"], person["id"], [(0, 5)])

    itself = link(api, first["id"], works["id"], ada, ada)
    assert itself["status"] == "invalid"
    assert "two different shapes" in (itself["error"] or "")

    elsewhere = link(api, first["id"], works["id"], ada, grace)
    assert elsewhere["status"] == "invalid"
    assert "same document" in (elsewhere["error"] or "")

    missing = link(api, first["id"], works["id"], ada, str(uuid.uuid4()))
    assert missing["status"] == "invalid"
    assert "same document" in (missing["error"] or "")

    # A tag is about the document as a whole, so it is not something a relation can join.
    tag = str(uuid.uuid4())
    api.post(
        f"{API}/images/{first['id']}/annotations:batch",
        json={
            "ops": [
                {
                    "op": "create",
                    "id": tag,
                    "type": "tag",
                    "class_id": person["id"],
                    "geometry": {},
                }
            ]
        },
    )
    wrong = link(api, first["id"], works["id"], ada, tag)
    assert wrong["status"] == "invalid"
    assert "two spans" in (wrong["error"] or "")


def test_removing_a_span_takes_its_relations_with_it(api: TestClient) -> None:
    project = relation_project(api, "Tidy up")
    add_file(api, project, "who.txt", "Ada works at Katib.")
    [document] = items(api, project)
    person = api.post(f"{API}/projects/{project}/classes", json={"name": "person"}).json()
    works = api.post(f"{API}/projects/{project}/classes", json={"name": "works for"}).json()
    ada, katib = spans_on(api, document["id"], person["id"], [(0, 3), (13, 18)])
    assert link(api, document["id"], works["id"], ada, katib)["status"] == "ok"

    res = api.post(
        f"{API}/images/{document['id']}/annotations:batch",
        json={"ops": [{"op": "delete", "id": katib}]},
    )
    assert res.json()["results"][0]["status"] == "ok", res.text

    # The span it pointed at is gone, so the relation cannot be left hanging.
    left = api.get(f"{API}/images/{document['id']}/annotations").json()
    assert [s["type"] for s in left] == ["span"]
    assert left[0]["id"] == ada


def test_relations_belong_to_a_project_of_text(api: TestClient) -> None:
    # Asking for relations says the project holds text, because that is where spans live.
    implied = api.post(
        f"{API}/projects", json={"name": "Links", "annotation_types": ["span", "relation"]}
    )
    assert implied.status_code == 201, implied.text
    assert implied.json()["medium"] == "text"

    # Saying it holds pictures instead is a contradiction, and is refused.
    wrong = api.post(
        f"{API}/projects",
        json={"name": "Pictures with links", "annotation_types": ["relation"], "medium": "image"},
    )
    assert wrong.status_code == 422, wrong.text
    assert "cannot use relation" in wrong.json()["message"]


def test_spans_and_the_link_between_them_can_arrive_together(api: TestClient) -> None:
    """The browser saves a batch of edits at once, so a link can arrive with its own spans."""
    project = relation_project(api, "One batch")
    add_file(api, project, "who.txt", "Ada works at Katib.")
    [document] = items(api, project)
    person = api.post(f"{API}/projects/{project}/classes", json={"name": "person"}).json()
    works = api.post(f"{API}/projects/{project}/classes", json={"name": "works for"}).json()
    ada, katib = str(uuid.uuid4()), str(uuid.uuid4())
    res = api.post(
        f"{API}/images/{document['id']}/annotations:batch",
        json={
            "ops": [
                {
                    "op": "create",
                    "id": ada,
                    "type": "span",
                    "class_id": person["id"],
                    "geometry": {"start": 0, "end": 3},
                },
                {
                    "op": "create",
                    "id": katib,
                    "type": "span",
                    "class_id": person["id"],
                    "geometry": {"start": 13, "end": 18},
                },
                {
                    "op": "create",
                    "id": str(uuid.uuid4()),
                    "type": "relation",
                    "class_id": works["id"],
                    "geometry": {"from_id": ada, "to_id": katib},
                },
            ]
        },
    )
    assert [r["status"] for r in res.json()["results"]] == ["ok", "ok", "ok"], res.text
