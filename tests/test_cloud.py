"""Reading a bucket, against a stand-in for the real thing.

The point of these is the parts Katib writes itself: the signature, the paging through a listing,
and turning a refusal into something worth reading.
"""

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from katib.storage import cloud

PAGE_ONE = """<?xml version="1.0"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Contents><Key>photos/a.jpg</Key><Size>12</Size></Contents>
  <Contents><Key>photos/</Key><Size>0</Size></Contents>
  <IsTruncated>true</IsTruncated>
  <NextContinuationToken>more</NextContinuationToken>
</ListBucketResult>"""

PAGE_TWO = """<?xml version="1.0"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Contents><Key>photos/b.png</Key><Size>34</Size></Contents>
  <IsTruncated>false</IsTruncated>
</ListBucketResult>"""

AZURE_PAGE = """<?xml version="1.0"?>
<EnumerationResults>
  <Blobs>
    <Blob><Name>photos/c.jpg</Name><Properties><Content-Length>9</Content-Length></Properties></Blob>
    <Blob><Name>photos/</Name><Properties><Content-Length>0</Content-Length></Properties></Blob>
  </Blobs>
  <NextMarker />
</EnumerationResults>"""


class Bucket(BaseHTTPRequestHandler):
    """Answers the few requests Katib makes, and records what it was asked."""

    seen: list[tuple[str, dict[str, list[str]], dict[str, str]]] = []
    refuse = False

    def do_GET(self) -> None:  # noqa: N802 -- the name http.server looks for
        parts = urlsplit(self.path)
        query = parse_qs(parts.query)
        # Header names are case-insensitive, so they are kept in one case here.
        sent = {name.lower(): value for name, value in self.headers.items()}
        Bucket.seen.append((parts.path, query, sent))
        if Bucket.refuse:
            self.send_error(403, "Forbidden")
            return
        if query.get("comp") == ["list"]:
            return self._send(AZURE_PAGE.encode())
        if query.get("list-type") == ["2"]:
            page = PAGE_TWO if query.get("continuation-token") else PAGE_ONE
            return self._send(page.encode())
        self._send(b"x" * 12)

    def _send(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        return


@pytest.fixture
def bucket() -> Iterator[str]:
    Bucket.seen = []
    Bucket.refuse = False
    server = ThreadingHTTPServer(("127.0.0.1", 0), Bucket)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


def s3(endpoint: str, **extra: Any) -> cloud.Source:
    return cloud.Source(
        name="pictures",
        provider="s3",
        bucket="my-bucket",
        access_key="AKIAEXAMPLE",
        secret="wJalrXUtnFEMI",
        region="eu-west-1",
        endpoint=endpoint,
        **extra,
    )


def test_a_listing_follows_its_pages_and_leaves_out_folders(bucket: str) -> None:
    found = cloud.list_objects(s3(bucket), "photos/")
    assert [(o.key, o.size) for o in found] == [("photos/a.jpg", 12), ("photos/b.png", 34)]
    # Two requests, the second carrying the token the first one gave back.
    assert len(Bucket.seen) == 2
    assert Bucket.seen[0][1]["prefix"] == ["photos/"]
    assert Bucket.seen[1][1]["continuation-token"] == ["more"]


def test_a_signed_request_carries_what_s3_expects(bucket: str) -> None:
    cloud.list_objects(s3(bucket), "photos/")
    path, _query, headers = Bucket.seen[0]
    # With an endpoint of its own, the bucket goes in the path.
    assert path == "/my-bucket"
    assert headers["authorization"].startswith("AWS4-HMAC-SHA256 Credential=AKIAEXAMPLE/")
    assert "/eu-west-1/s3/aws4_request" in headers["authorization"]
    assert "SignedHeaders=host;x-amz-content-sha256;x-amz-date" in headers["authorization"]
    assert headers["x-amz-content-sha256"] == cloud.EMPTY_SHA256
    assert "Signature=" in headers["authorization"]


def test_the_same_request_signs_the_same_way_twice(bucket: str) -> None:
    """A signature that moved on its own would be a signing bug, not a clock."""
    first = cloud._s3_request(s3(bucket), "GET", "photos/a.jpg", {})
    second = cloud._s3_request(s3(bucket), "GET", "photos/a.jpg", {})
    if first.headers["X-amz-date"] == second.headers["X-amz-date"]:
        assert first.headers["Authorization"] == second.headers["Authorization"]
    assert first.full_url == second.full_url


def test_amazon_itself_is_addressed_with_the_bucket_in_the_host() -> None:
    request = cloud._s3_request(s3(""), "GET", "photos/a.jpg", {})
    assert request.full_url == "https://my-bucket.s3.eu-west-1.amazonaws.com/photos/a.jpg"


def test_an_object_comes_back_and_an_oversized_one_is_refused(bucket: str) -> None:
    assert cloud.fetch(s3(bucket), "photos/a.jpg", 1024) == b"x" * 12
    with pytest.raises(cloud.CloudError, match="larger than"):
        cloud.fetch(s3(bucket), "photos/a.jpg", 4)


def test_a_refusal_says_what_to_check(bucket: str) -> None:
    Bucket.refuse = True
    with pytest.raises(cloud.CloudError, match="access key"):
        cloud.list_objects(s3(bucket), "photos/")


def test_an_endpoint_that_is_not_a_web_address_is_refused() -> None:
    with pytest.raises(cloud.CloudError, match="http or https"):
        cloud.list_objects(s3("file:///etc"), "photos/")


def test_azure_lists_blobs_and_signs_with_a_shared_key(bucket: str) -> None:
    source = cloud.Source(
        name="azure",
        provider="azure",
        bucket="pictures",
        access_key="myaccount",
        secret="c2VjcmV0",  # base64, the way the portal gives it
        endpoint=bucket,
    )
    found = cloud.list_objects(source, "photos/")
    assert [(o.key, o.size) for o in found] == [("photos/c.jpg", 9)]
    path, query, headers = Bucket.seen[0]
    assert path == "/pictures"
    assert query["restype"] == ["container"]
    assert headers["authorization"].startswith("SharedKey myaccount:")
    assert headers["x-ms-version"] == cloud.AZURE_VERSION


def test_an_azure_key_that_is_not_base64_says_so(bucket: str) -> None:
    source = cloud.Source(
        name="azure",
        provider="azure",
        bucket="pictures",
        access_key="myaccount",
        secret="not base64 !!",
        endpoint=bucket,
    )
    with pytest.raises(cloud.CloudError, match="base64"):
        cloud.list_objects(source, "photos/")
