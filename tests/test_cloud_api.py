"""Setting up a bucket and bringing its pictures into a project, against a stand-in bucket."""

import io
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage

from katib.api.app import create_app
from katib.config import Settings

API = "/api/v1"

LISTING = """<?xml version="1.0"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Contents><Key>sets/train/one.png</Key><Size>120</Size></Contents>
  <Contents><Key>sets/train/notes.txt</Key><Size>10</Size></Contents>
  <IsTruncated>false</IsTruncated>
</ListBucketResult>"""


def png(color: str) -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGB", (40, 30), color).save(buffer, "PNG")
    return buffer.getvalue()


class Bucket(BaseHTTPRequestHandler):
    asked: list[str] = []

    def do_GET(self) -> None:  # noqa: N802 -- the name http.server looks for
        parts = urlsplit(self.path)
        Bucket.asked.append(parts.path)
        if parse_qs(parts.query).get("list-type") == ["2"]:
            return self._send(LISTING.encode(), "application/xml")
        self._send(png("red"), "image/png")

    def _send(self, body: bytes, kind: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        return


@pytest.fixture
def bucket() -> Iterator[str]:
    Bucket.asked = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Bucket)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def api(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(storage={"data_dir": str(tmp_path / "data")}))) as c:
        yield c


def details(endpoint: str) -> dict[str, str]:
    return {
        "name": "photos",
        "provider": "s3",
        "bucket": "my-bucket",
        "access_key": "AKIAEXAMPLE",
        "secret": "wJalrXUtnFEMI",
        "region": "eu-west-1",
        "endpoint": endpoint,
    }


def wait(api: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(400):
        job = api.get(f"{API}/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError("the job did not finish")


def test_a_bucket_is_checked_before_it_is_kept_and_its_key_never_comes_back(
    api: TestClient, bucket: str, tmp_path: Path
) -> None:
    saved = api.put(f"{API}/settings/cloud", json=details(bucket))
    assert saved.status_code == 200, saved.text
    assert saved.json() == {"objects": 2}

    listed = api.get(f"{API}/settings/cloud").json()
    assert [s["name"] for s in listed] == ["photos"]
    assert "secret" not in listed[0]
    assert listed[0]["bucket"] == "my-bucket"

    # The secret is on the server, in a file of its own.
    kept = (tmp_path / "data" / "cloud-sources.json").read_text(encoding="utf-8")
    assert "wJalrXUtnFEMI" in kept


def test_details_that_do_not_work_are_refused(api: TestClient) -> None:
    wrong = details("http://127.0.0.1:1")
    refused = api.put(f"{API}/settings/cloud", json=wrong)
    assert refused.status_code == 422
    assert "reach the bucket" in refused.json()["message"].lower()
    assert api.get(f"{API}/settings/cloud").json() == []

    nameless = api.put(f"{API}/settings/cloud", json={**details(""), "name": " "})
    assert nameless.status_code == 422


def test_pictures_in_a_bucket_are_labelled_without_copying_them_in(
    api: TestClient, bucket: str, tmp_path: Path
) -> None:
    api.put(f"{API}/settings/cloud", json=details(bucket))
    project = api.post(f"{API}/projects", json={"name": "From the bucket"}).json()["id"]

    started = api.post(
        f"{API}/projects/{project}/cloud-imports", json={"source": "photos", "prefix": "sets/"}
    )
    assert started.status_code == 202, started.text
    job = wait(api, started.json()["id"])
    assert job["status"] == "done", job
    # The .txt in the listing is not a picture, so it is left alone without a complaint.
    assert job["result"]["added"] == 1
    assert job["result"]["skipped_count"] == 0

    [item] = api.get(f"{API}/projects/{project}/images").json()["items"]
    assert item["filename"] == "one.png"
    assert item["width"] == 40 and item["height"] == 30
    # The folder it sat in says which split it belongs to.
    assert item["split"] == "train"

    # The picture itself is served, and its thumbnail was made when it came in.
    assert api.get(f"{API}/images/{item['id']}/file").status_code == 200
    assert api.get(f"{API}/images/{item['id']}/thumb").status_code == 200

    # Nothing was written into the uploads folder: the picture stays in the bucket.
    uploads = tmp_path / "data" / "uploads"
    assert not uploads.exists() or not list(uploads.rglob("*.png"))

    # Running it again brings in nothing new.
    again = wait(
        api,
        api.post(
            f"{API}/projects/{project}/cloud-imports", json={"source": "photos", "prefix": "sets/"}
        ).json()["id"],
    )
    assert again["result"]["added"] == 0


def test_the_picture_is_only_fetched_once(api: TestClient, bucket: str) -> None:
    api.put(f"{API}/settings/cloud", json=details(bucket))
    project = api.post(f"{API}/projects", json={"name": "Cache"}).json()["id"]
    wait(
        api,
        api.post(f"{API}/projects/{project}/cloud-imports", json={"source": "photos"}).json()["id"],
    )
    [item] = api.get(f"{API}/projects/{project}/images").json()["items"]
    before = Bucket.asked.count("/my-bucket/sets/train/one.png")
    for _ in range(3):
        assert api.get(f"{API}/images/{item['id']}/file").status_code == 200
    assert Bucket.asked.count("/my-bucket/sets/train/one.png") == before


def test_forgetting_a_bucket(api: TestClient, bucket: str) -> None:
    api.put(f"{API}/settings/cloud", json=details(bucket))
    assert api.delete(f"{API}/settings/cloud/photos").status_code == 204
    assert api.get(f"{API}/settings/cloud").json() == []
    assert api.delete(f"{API}/settings/cloud/photos").status_code == 404


def test_importing_from_a_bucket_that_is_not_set_up_says_so(api: TestClient) -> None:
    project = api.post(f"{API}/projects", json={"name": "None"}).json()["id"]
    missing = api.post(f"{API}/projects/{project}/cloud-imports", json={"source": "nope"})
    assert missing.status_code == 404


def test_the_cache_of_fetched_pictures_is_kept_within_its_limit(
    api: TestClient, bucket: str, tmp_path: Path
) -> None:
    """A big bucket must not fill the disk: the oldest fetched pictures go first."""
    api.put(f"{API}/settings/cloud", json=details(bucket))
    project = api.post(f"{API}/projects", json={"name": "Cache limit"}).json()["id"]
    wait(
        api,
        api.post(f"{API}/projects/{project}/cloud-imports", json={"source": "photos"}).json()["id"],
    )
    cache = tmp_path / "data" / "cloud-cache"
    assert list(cache.rglob("*.png")), "the picture should be in the cache"

    # With room for almost nothing, the next prune clears what is there.
    storage = api.app.state.storage  # type: ignore[attr-defined]
    from katib.services import cloud_sources

    object.__setattr__(storage, "max_cloud_cache_bytes", 10)
    dropped = cloud_sources.prune_cache(storage, force=True)
    assert dropped > 0
    assert not list(cache.rglob("*.png"))

    # The picture is still served: it is fetched again and cached again.
    [item] = api.get(f"{API}/projects/{project}/images").json()["items"]
    object.__setattr__(storage, "max_cloud_cache_bytes", 5_000 * 1024 * 1024)
    assert api.get(f"{API}/images/{item['id']}/file").status_code == 200
    assert list(cache.rglob("*.png"))
