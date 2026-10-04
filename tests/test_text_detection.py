"""Telling the text formats apart.

Four of them read `.jsonl` files and two read loose files in a folder, so each has to claim only
what is really its own. These tests write one file of every shape and check that exactly the
right format recognises it, which is what makes connecting a folder guess correctly.
"""

import json
from pathlib import Path

import pytest

from katib.formats import REGISTRY, detect_format
from katib.formats.common import FormatError


def write(folder: Path, name: str, body: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(body, encoding="utf-8")
    return path


def conll_file(folder: Path) -> Path:
    return write(
        folder,
        "documents.conll",
        "Ada B-person\nworks O\nat O\nKatib B-org\n. O\n",
    )


def hf_file(folder: Path) -> Path:
    return write(
        folder,
        "documents.jsonl",
        json.dumps({"tokens": ["Ada", "works"], "ner_tags": ["B-person", "O"]}) + "\n",
    )


def katib_file(folder: Path) -> Path:
    return write(
        folder,
        "documents.jsonl",
        json.dumps(
            {"id": "a", "text": "Ada works.", "spans": [{"start": 0, "end": 3, "label": "person"}]}
        )
        + "\n",
    )


def studio_file(folder: Path) -> Path:
    return write(
        folder,
        "tasks.json",
        json.dumps(
            [
                {
                    "data": {"text": "Ada works at Katib."},
                    "annotations": [
                        {
                            "result": [
                                {
                                    "type": "labels",
                                    "value": {"start": 0, "end": 3, "labels": ["person"]},
                                }
                            ]
                        }
                    ],
                }
            ]
        ),
    )


def brat_files(folder: Path) -> Path:
    write(folder, "who.txt", "Ada works at Katib.")
    write(folder, "who.ann", "T1\tperson 0 3\tAda\n")
    return folder / "who.ann"


def classes_file(folder: Path) -> Path:
    return write(folder, "documents.csv", "text,label\nKatib runs well.,positive\n")


MAKERS = {
    "conll": conll_file,
    "hf-tokens": hf_file,
    "jsonl-spans": katib_file,
    "label-studio": studio_file,
    "brat": brat_files,
    "text-class": classes_file,
}


@pytest.mark.parametrize("wanted", sorted(MAKERS))
def test_each_text_format_claims_only_its_own_files(tmp_path: Path, wanted: str) -> None:
    folder = tmp_path / wanted
    MAKERS[wanted](folder)
    claimed = sorted(f.id for f in REGISTRY.values() if f.detect(folder))
    assert claimed == [wanted], f"{wanted} was also claimed by {set(claimed) - {wanted}}"


@pytest.mark.parametrize("wanted", sorted(MAKERS))
def test_a_folder_of_each_shape_is_recognised_on_its_own(tmp_path: Path, wanted: str) -> None:
    """What connecting a folder does: work out the format without being told."""
    folder = tmp_path / wanted
    MAKERS[wanted](folder)
    assert detect_format(folder).id == wanted


def test_a_file_of_plain_text_is_not_a_set_of_labels(tmp_path: Path) -> None:
    """Words with nothing marked on them are documents to add, not labels to read onto them."""
    folder = tmp_path / "plain"
    write(folder, "documents.jsonl", json.dumps({"text": "Ada works at Katib."}) + "\n")
    assert [f.id for f in REGISTRY.values() if f.detect(folder)] == []
    with pytest.raises(FormatError):
        detect_format(folder)


def test_a_spacy_file_is_claimed_by_the_one_format_that_reads_it(tmp_path: Path) -> None:
    """spaCy's triples are the same file as Katib's own spans, so one format reads both."""
    folder = tmp_path / "spacy"
    write(
        folder,
        "documents.jsonl",
        json.dumps({"text": "Ada works at Katib.", "entities": [[0, 3, "person"]]}) + "\n",
    )
    assert [f.id for f in REGISTRY.values() if f.detect(folder)] == ["jsonl-spans"]


def test_a_picture_dataset_is_not_claimed_by_a_text_format(tmp_path: Path) -> None:
    folder = tmp_path / "pictures"
    write(folder, "metadata.jsonl", json.dumps({"file_name": "a.jpg", "tags": ["street"]}) + "\n")
    claimed = sorted(f.id for f in REGISTRY.values() if f.detect(folder))
    assert claimed == ["jsonl"]
