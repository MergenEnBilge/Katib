"""The text formats: what each one writes, and that reading it back gives the same labels.

Every one of these goes out of Katib and comes back into a fresh project, because a format that
writes a file nothing can read again is no use. The round trip is done through the API so that
the job runner, the import matching and the document making are all in the path.
"""

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
REVIEW = "Ada works at Katib. Grace wrote COBOL."


@pytest.fixture
def api(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(storage={"data_dir": str(tmp_path / "data")})
    with TestClient(create_app(settings)) as c:
        yield c


def wait(api: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(400):
        job = api.get(f"{API}/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError("the job did not finish")


def text_project(api: TestClient, name: str, types: list[str] | None = None) -> str:
    made = api.post(
        f"{API}/projects",
        json={"name": name, "annotation_types": types or ["span", "tag", "text"]},
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def add_document(api: TestClient, project: str, name: str, body: str) -> dict[str, Any]:
    res = api.post(
        f"{API}/projects/{project}/documents",
        files={"file": (name, body.encode("utf-8"), "text/plain")},
    )
    assert res.status_code == 202, res.text
    job = wait(api, res.json()["id"])
    assert job["status"] == "done", job
    return dict(api.get(f"{API}/projects/{project}/images").json()["items"][0])


def label(api: TestClient, project: str, name: str) -> str:
    return str(api.post(f"{API}/projects/{project}/classes", json={"name": name}).json()["id"])


def put(api: TestClient, document: str, ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    res = api.post(f"{API}/images/{document}/annotations:batch", json={"ops": ops})
    assert res.status_code == 200, res.text
    results = [dict(r) for r in res.json()["results"]]
    assert all(r["status"] == "ok" for r in results), results
    return results


def span(class_id: str, start: int, end: int) -> dict[str, Any]:
    return {
        "op": "create",
        "id": str(uuid.uuid4()),
        "type": "span",
        "class_id": class_id,
        "geometry": {"start": start, "end": end},
    }


def export(api: TestClient, project: str, fmt: str, dest: Path) -> dict[str, Any]:
    started = api.post(
        f"{API}/projects/{project}/exports", json={"format": fmt, "destination": str(dest)}
    )
    assert started.status_code == 202, started.text
    job = wait(api, started.json()["id"])
    assert job["status"] == "done", job
    return dict(job["result"])


def read_back(api: TestClient, project: str, path: Path, fmt: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"path": str(path)}
    if fmt:
        body["format"] = fmt
    started = api.post(f"{API}/projects/{project}/imports", json=body)
    assert started.status_code == 202, started.text
    job = wait(api, started.json()["id"])
    assert job["status"] == "done", job
    return dict(job["result"])


def labelled(api: TestClient, project: str) -> set[tuple[str, str]]:
    """Every span in a project, as the words it covers and the class on it."""
    out: set[tuple[str, str]] = set()
    for item in api.get(f"{API}/projects/{project}/images", params={"limit": 200}).json()["items"]:
        words = api.get(f"{API}/images/{item['id']}/text").json()["text"]
        classes = {c["id"]: c["name"] for c in api.get(f"{API}/projects/{project}/classes").json()}
        for shape in api.get(f"{API}/images/{item['id']}/annotations").json():
            if shape["type"] == "span":
                start, end = shape["geometry"]["start"], shape["geometry"]["end"]
                out.add((words[start:end], classes[shape["class_id"]]))
    return out


def spans_project(api: TestClient, name: str) -> tuple[str, str]:
    """A project with one document, "Ada" marked as a person and "COBOL" as a language."""
    project = text_project(api, name)
    document = add_document(api, project, "review.txt", REVIEW)
    person = label(api, project, "person")
    language = label(api, project, "language")
    put(
        api,
        document["id"],
        [span(person, 0, 3), span(language, 32, 37)],
    )
    return project, document["id"]


EXPECTED = {("Ada", "person"), ("COBOL", "language")}


@pytest.mark.parametrize(
    ("fmt", "written"),
    [
        ("jsonl-spans", "documents.jsonl"),
        ("conll", "documents.conll"),
        ("hf-tokens", "documents.jsonl"),
        ("label-studio", "tasks.json"),
        ("brat", "review.ann"),
    ],
    ids=["katib", "conll", "hugging-face", "label-studio", "brat"],
)
def test_spans_survive_a_round_trip(
    api: TestClient, tmp_path: Path, fmt: str, written: str
) -> None:
    project, _ = spans_project(api, f"Out {fmt}")
    dest = tmp_path / f"out-{fmt}"
    report = export(api, project, fmt, dest)
    assert report["images"] == 1
    assert (dest / written).is_file()

    # Into a project with nothing in it: each of these formats carries its own words, so the
    # documents are made from the file rather than having to be there already.
    back = text_project(api, f"Back {fmt}")
    result = read_back(api, back, dest, fmt)
    assert result["format"] == fmt
    assert result["documents_added"] == 1, result
    assert labelled(api, back) == EXPECTED


def test_conll_writes_one_word_per_line_with_bio_tags(api: TestClient, tmp_path: Path) -> None:
    project, _ = spans_project(api, "CoNLL shape")
    dest = tmp_path / "conll"
    export(api, project, "conll", dest)
    lines = (dest / "documents.conll").read_text(encoding="utf-8").splitlines()
    rows = [line.split() for line in lines if line and not line.startswith("#")]
    assert rows[0] == ["Ada", "B-person"]
    assert rows[1] == ["works", "O"]
    assert ["COBOL", "B-language"] in rows


def test_hugging_face_writes_tokens_with_a_label_set(api: TestClient, tmp_path: Path) -> None:
    project, _ = spans_project(api, "Hugging Face shape")
    dest = tmp_path / "hf"
    export(api, project, "hf-tokens", dest)
    row = json.loads((dest / "documents.jsonl").read_text(encoding="utf-8").strip())
    assert row["tokens"][:3] == ["Ada", "works", "at"]
    assert row["ner_tags"][0] == "B-person"
    # The usual training scripts want the label set up front.
    labels = (dest / "labels.txt").read_text(encoding="utf-8").split()
    assert "O" in labels and "B-person" in labels


def test_the_spans_file_is_written_under_every_name_it_is_read_by(
    api: TestClient, tmp_path: Path
) -> None:
    """One JSON Lines file, which spaCy, Prodigy and Katib all read, rather than one each."""
    project, _ = spans_project(api, "spaCy shape")
    dest = tmp_path / "spans"
    export(api, project, "jsonl-spans", dest)
    row = json.loads((dest / "documents.jsonl").read_text(encoding="utf-8").strip())
    assert row["text"] == REVIEW
    # Katib's own named spans, and the triples spaCy's loaders look for.
    assert {"start": 0, "end": 3, "label": "person", "text": "Ada"} in row["spans"]
    assert [0, 3, "person"] in row["entities"]


def test_a_file_written_by_spacy_or_prodigy_is_read(api: TestClient, tmp_path: Path) -> None:
    """The shapes those tools write, which name the same things differently."""
    folder = tmp_path / "from-spacy"
    folder.mkdir()
    (folder / "documents.jsonl").write_text(
        json.dumps(
            {
                "id": "review",
                "text": "Ada works at Katib.",
                "entities": [[0, 3, "person"], [13, 18, "org"]],
                "accept": ["positive"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    project = text_project(api, "From spaCy")
    result = read_back(api, project, folder, "jsonl-spans")
    assert result["documents_added"] == 1, result
    assert labelled(api, project) == {("Ada", "person"), ("Katib", "org")}
    [item] = api.get(f"{API}/projects/{project}/images").json()["items"]
    kinds = sorted(s["type"] for s in api.get(f"{API}/images/{item['id']}/annotations").json())
    assert kinds == ["span", "span", "tag"]


def test_a_span_that_cuts_a_word_is_reported_not_hidden(api: TestClient, tmp_path: Path) -> None:
    """One word per line cannot hold half a word, so it grows, and the export says so."""
    project = text_project(api, "Half a word")
    document = add_document(api, project, "review.txt", "Katibs everywhere.")
    product = label(api, project, "product")
    put(api, document["id"], [span(product, 0, 5)])
    report = export(api, project, "conll", tmp_path / "cut")
    assert any("stretched" in note["reason"] for note in report["notes"]), report["notes"]


def test_relations_go_out_and_come_back_in_brat(api: TestClient, tmp_path: Path) -> None:
    project = text_project(api, "Brat links", ["span", "relation"])
    document = add_document(api, project, "who.txt", "Ada works at Katib.")
    person = label(api, project, "person")
    works = label(api, project, "works for")
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    put(
        api,
        document["id"],
        [
            {**span(person, 0, 3), "id": first},
            {**span(person, 13, 18), "id": second},
            {
                "op": "create",
                "id": str(uuid.uuid4()),
                "type": "relation",
                "class_id": works,
                "geometry": {"from_id": first, "to_id": second},
            },
        ],
    )
    dest = tmp_path / "brat"
    export(api, project, "brat", dest)
    written = (dest / "who.ann").read_text(encoding="utf-8")
    assert "T1\tperson 0 3\tAda" in written
    assert "R1\tworks_for Arg1:T1 Arg2:T2" in written

    back = text_project(api, "Brat links back", ["span", "relation"])
    result = read_back(api, back, dest, "brat")
    assert result["shapes_added"] == 3, result
    [item] = api.get(f"{API}/projects/{back}/images").json()["items"]
    kinds = sorted(s["type"] for s in api.get(f"{API}/images/{item['id']}/annotations").json())
    assert kinds == ["relation", "span", "span"]


def test_relations_go_out_and_come_back_in_label_studio(api: TestClient, tmp_path: Path) -> None:
    project = text_project(api, "Studio links", ["span", "relation", "tag"])
    document = add_document(api, project, "who.txt", "Ada works at Katib.")
    person = label(api, project, "person")
    works = label(api, project, "works for")
    mood = label(api, project, "positive")
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    put(
        api,
        document["id"],
        [
            {**span(person, 0, 3), "id": first},
            {**span(person, 13, 18), "id": second},
            {
                "op": "create",
                "id": str(uuid.uuid4()),
                "type": "relation",
                "class_id": works,
                "geometry": {"from_id": first, "to_id": second},
            },
            {
                "op": "create",
                "id": str(uuid.uuid4()),
                "type": "tag",
                "class_id": mood,
                "geometry": {},
            },
        ],
    )
    dest = tmp_path / "studio"
    export(api, project, "label-studio", dest)
    [task] = json.loads((dest / "tasks.json").read_text(encoding="utf-8"))
    kinds = sorted(r["type"] for r in task["annotations"][0]["result"])
    assert kinds == ["choices", "labels", "labels", "relation"]

    back = text_project(api, "Studio links back", ["span", "relation", "tag"])
    result = read_back(api, back, dest, "label-studio")
    assert result["shapes_added"] == 4, result


def test_a_label_for_a_whole_document_round_trips_as_csv(api: TestClient, tmp_path: Path) -> None:
    project = text_project(api, "Sorting", ["tag", "text"])
    document = add_document(api, project, "review.txt", "Katib runs on my laptop.")
    mood = label(api, project, "positive")
    put(
        api,
        document["id"],
        [
            {
                "op": "create",
                "id": str(uuid.uuid4()),
                "type": "tag",
                "class_id": mood,
                "geometry": {},
            },
            {
                "op": "create",
                "id": str(uuid.uuid4()),
                "type": "text",
                "class_id": None,
                "geometry": {"text": "Praise for the app."},
            },
        ],
    )
    dest = tmp_path / "csv"
    export(api, project, "text-class", dest)
    written = (dest / "documents.csv").read_text(encoding="utf-8")
    assert "text,label,answer,split" in written
    assert "positive" in written and "Praise for the app." in written

    back = text_project(api, "Sorting back", ["tag", "text"])
    result = read_back(api, back, dest, "text-class")
    assert result["documents_added"] == 1, result
    [item] = api.get(f"{API}/projects/{back}/images").json()["items"]
    kinds = sorted(s["type"] for s in api.get(f"{API}/images/{item['id']}/annotations").json())
    assert kinds == ["tag", "text"]


def test_the_csv_export_says_it_cannot_hold_spans(api: TestClient, tmp_path: Path) -> None:
    project, _ = spans_project(api, "Spans as csv")
    report = export(api, project, "text-class", tmp_path / "flat")
    assert any("left out" in note["reason"] for note in report["notes"]), report["notes"]
