"""Fetching a known model, without ever touching the real network.

A tiny local HTTP server stands in for the real download host, so these tests exercise the same
streaming, size-checking and hash-checking code the real thing runs, just against bytes this file
made itself.
"""

import hashlib
import io
import threading
import zipfile
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from katib.ml import sam
from katib.services import model_downloads as md
from katib.services.errors import InvalidInput


def make_zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buffer.getvalue()


@pytest.fixture
def server() -> Iterator[tuple[HTTPServer, dict[str, bytes]]]:
    served: dict[str, bytes] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            body = served.get(self.path)
            if body is None:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd, served
    finally:
        httpd.shutdown()
        thread.join()


def url_for(httpd: HTTPServer, path: str) -> str:
    return f"http://127.0.0.1:{httpd.server_port}{path}"


def test_an_unknown_model_id_is_refused() -> None:
    with pytest.raises(InvalidInput):
        md.find("not-a-real-model")


def test_the_catalog_entries_are_findable() -> None:
    for entry in md.CATALOG:
        assert md.find(entry.id) is entry


def test_a_download_that_matches_its_hash_is_installed(
    server: tuple[HTTPServer, dict[str, bytes]], tmp_path: Path
) -> None:
    httpd, served = server
    payload = make_zip({"a.onnx": b"encoder bytes", "b.onnx": b"decoder bytes"})
    served["/model.zip"] = payload
    source = md.ModelSource(
        id="test",
        label="Test",
        help="",
        url=url_for(httpd, "/model.zip"),
        sha256=hashlib.sha256(payload).hexdigest(),
        bytes=len(payload),
        files={"a.onnx": sam.ENCODER_NAME, "b.onnx": sam.DECODER_NAME},
    )
    folder = tmp_path / "models"
    seen: list[float] = []
    md.download_and_install(source, folder, seen.append)

    assert (folder / sam.ENCODER_NAME).read_bytes() == b"encoder bytes"
    assert (folder / sam.DECODER_NAME).read_bytes() == b"decoder bytes"
    assert seen and seen[-1] == pytest.approx(1.0)


def test_a_download_that_does_not_match_its_hash_is_refused(
    server: tuple[HTTPServer, dict[str, bytes]], tmp_path: Path
) -> None:
    httpd, served = server
    payload = make_zip({"a.onnx": b"encoder bytes", "b.onnx": b"decoder bytes"})
    served["/model.zip"] = payload
    source = md.ModelSource(
        id="test",
        label="Test",
        help="",
        url=url_for(httpd, "/model.zip"),
        sha256="0" * 64,
        bytes=len(payload),
        files={"a.onnx": sam.ENCODER_NAME, "b.onnx": sam.DECODER_NAME},
    )
    folder = tmp_path / "models"
    with pytest.raises(InvalidInput, match="did not match"):
        md.download_and_install(source, folder)
    assert not folder.exists() or not any(folder.iterdir())


def test_a_download_bigger_than_expected_is_stopped(
    server: tuple[HTTPServer, dict[str, bytes]], tmp_path: Path
) -> None:
    httpd, served = server
    payload = make_zip({"a.onnx": b"x" * 10_000, "b.onnx": b"y"})
    served["/model.zip"] = payload
    source = md.ModelSource(
        id="test",
        label="Test",
        help="",
        url=url_for(httpd, "/model.zip"),
        sha256=hashlib.sha256(payload).hexdigest(),
        bytes=10,
        files={"a.onnx": sam.ENCODER_NAME, "b.onnx": sam.DECODER_NAME},
    )
    with pytest.raises(InvalidInput, match="larger than expected"):
        md.download_and_install(source, tmp_path / "models")


def test_a_zip_missing_the_expected_files_is_refused(
    server: tuple[HTTPServer, dict[str, bytes]], tmp_path: Path
) -> None:
    httpd, served = server
    payload = make_zip({"unrelated.txt": b"nope"})
    served["/model.zip"] = payload
    source = md.ModelSource(
        id="test",
        label="Test",
        help="",
        url=url_for(httpd, "/model.zip"),
        sha256=hashlib.sha256(payload).hexdigest(),
        bytes=len(payload),
        files={"a.onnx": sam.ENCODER_NAME, "b.onnx": sam.DECODER_NAME},
    )
    with pytest.raises(InvalidInput, match="did not have the files"):
        md.download_and_install(source, tmp_path / "models")


def test_a_host_that_cannot_be_reached_says_so(tmp_path: Path) -> None:
    source = md.ModelSource(
        id="test",
        label="Test",
        help="",
        url="http://127.0.0.1:1/model.zip",
        sha256="0" * 64,
        bytes=10,
        files={},
    )
    with pytest.raises(InvalidInput, match="Could not reach"):
        md.download_and_install(source, tmp_path / "models")
