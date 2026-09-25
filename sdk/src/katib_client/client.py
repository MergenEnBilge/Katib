"""The client. Each part of the server has a small object on `Katib`: projects, classes, images,
annotations, and the calls that move whole datasets in and out."""

from __future__ import annotations

import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

API = "/api/v1"
POLL_SECONDS = 0.4


class KatibError(Exception):
    """The server said no. `code` is stable and `message` is written for people."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    image_count: int
    done_count: int
    annotation_types: list[str]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Project:
        return cls(
            id=data["id"],
            name=data["name"],
            image_count=data.get("image_count", 0),
            done_count=data.get("done_count", 0),
            annotation_types=list(data.get("annotation_types", [])),
        )


@dataclass(frozen=True)
class ClassInfo:
    id: str
    name: str
    color: str
    annotation_count: int

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> ClassInfo:
        return cls(data["id"], data["name"], data["color"], data.get("annotation_count", 0))


@dataclass(frozen=True)
class ImageInfo:
    id: str
    filename: str
    width: int
    height: int
    status: str
    annotation_count: int

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> ImageInfo:
        return cls(
            id=data["id"],
            filename=data["filename"],
            width=data["width"],
            height=data["height"],
            status=data["status"],
            annotation_count=data.get("annotation_count", 0),
        )


@dataclass(frozen=True)
class Annotation:
    id: str
    image_id: str
    class_id: str | None
    type: str
    geometry: dict[str, Any]
    source: str
    confidence: float | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Annotation:
        return cls(
            id=data["id"],
            image_id=data["image_id"],
            class_id=data.get("class_id"),
            type=data["type"],
            geometry=data["geometry"],
            source=data["source"],
            confidence=data.get("confidence"),
        )


class Katib:
    """A connection to one Katib server.

    `token` is an API token from the server, needed when accounts are on. Pass `http` to use
    your own `httpx.Client`, for example to set timeouts or a proxy.
    """

    def __init__(
        self,
        url: str = "http://127.0.0.1:8420",
        token: str | None = None,
        *,
        http: httpx.Client | None = None,
    ) -> None:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._http = http or httpx.Client(base_url=url.rstrip("/"), timeout=60.0)
        self._http.headers.update(headers)
        self.projects = _Projects(self)
        self.classes = _Classes(self)
        self.images = _Images(self)
        self.annotations = _Annotations(self)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Katib:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Call the API. Returns the decoded JSON, or None when there is no body."""
        response = self._http.request(method, f"{API}{path}", **kwargs)
        if response.is_success:
            return response.json() if response.content else None
        try:
            body = response.json()
            raise KatibError(response.status_code, body["code"], body["message"])
        except (ValueError, KeyError):
            raise KatibError(
                response.status_code, "error", response.text or "Request failed."
            ) from None

    def health(self) -> dict[str, Any]:
        result: dict[str, Any] = self.request("GET", "/health")
        return result

    def wait_for(self, job_id: str, timeout: float = 600.0) -> dict[str, Any]:
        """Wait for a background job to finish and return it. Raises if it failed."""
        deadline = time.monotonic() + timeout
        while True:
            job: dict[str, Any] = self.request("GET", f"/jobs/{job_id}")
            if job["status"] == "done":
                return job
            if job["status"] == "failed":
                raise KatibError(500, "job_failed", job.get("error") or "The job failed.")
            if time.monotonic() > deadline:
                raise TimeoutError(f"Job {job_id} did not finish within {timeout:.0f} seconds.")
            time.sleep(POLL_SECONDS)

    def export(
        self,
        project_id: str,
        format: str,
        destination: str | Path,
        *,
        statuses: Sequence[str] | None = None,
        copy_images: bool = False,
        split: dict[str, float | int | bool] | None = None,
    ) -> Path:
        """Export a project and save the zip file. Returns where it was saved.

        `destination` is a folder (made if it does not exist) or a file name ending in `.zip`.
        `split` looks like
        `{"train": 0.8, "val": 0.1, "test": 0.1, "seed": 0, "stratify": True}`.
        """
        body: dict[str, Any] = {"format": format, "copy_images": copy_images}
        if statuses:
            body["statuses"] = list(statuses)
        if split:
            body["split"] = split
        started = self.request("POST", f"/projects/{project_id}/exports", json=body)
        job = self.wait_for(started["id"])
        target = Path(destination)
        if target.is_dir() or target.suffix != ".zip":
            target = target / job["result"]["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._http.stream("GET", f"{API}/jobs/{job['id']}/download") as response:
            if not response.is_success:
                raise KatibError(
                    response.status_code, "error", "The export could not be downloaded."
                )
            with target.open("wb") as out:
                for chunk in response.iter_bytes():
                    out.write(chunk)
        return target

    def import_labels(
        self, project_id: str, path: str | Path, format: str | None = None
    ) -> dict[str, Any]:
        """Add labels from a dataset folder or file that is on the *server's* computer."""
        body: dict[str, Any] = {"path": str(path)}
        if format:
            body["format"] = format
        started = self.request("POST", f"/projects/{project_id}/imports", json=body)
        result: dict[str, Any] = self.wait_for(started["id"])["result"]
        return result


class _Part:
    def __init__(self, katib: Katib) -> None:
        self._k = katib


class _Projects(_Part):
    def list(self) -> list[Project]:
        return [Project.from_api(p) for p in self._k.request("GET", "/projects")]

    def get(self, project_id: str) -> Project:
        return Project.from_api(self._k.request("GET", f"/projects/{project_id}"))

    def create(self, name: str, annotation_types: Sequence[str] | None = None) -> Project:
        """Make a project. `annotation_types` picks from box, polygon, obb, keypoints, mask, tag."""
        body: dict[str, Any] = {"name": name}
        if annotation_types:
            body["annotation_types"] = list(annotation_types)
        return Project.from_api(self._k.request("POST", "/projects", json=body))


class _Classes(_Part):
    def list(self, project_id: str) -> list[ClassInfo]:
        return [
            ClassInfo.from_api(c) for c in self._k.request("GET", f"/projects/{project_id}/classes")
        ]

    def create(self, project_id: str, name: str, color: str | None = None) -> ClassInfo:
        body: dict[str, Any] = {"name": name}
        if color:
            body["color"] = color
        return ClassInfo.from_api(
            self._k.request("POST", f"/projects/{project_id}/classes", json=body)
        )


class _Images(_Part):
    def list(
        self,
        project_id: str,
        *,
        status: str | None = None,
        has_annotations: bool | None = None,
        page_size: int = 200,
    ) -> Iterator[ImageInfo]:
        """Every image in the project, fetched a page at a time."""
        after: str | None = None
        while True:
            params: dict[str, Any] = {"limit": page_size}
            if status:
                params["status"] = status
            if has_annotations is not None:
                params["has_annotations"] = has_annotations
            if after:
                params["after"] = after
            page = self._k.request("GET", f"/projects/{project_id}/images", params=params)
            for item in page["items"]:
                yield ImageInfo.from_api(item)
            after = page["next"]
            if not after:
                return

    def upload(self, project_id: str, path: str | Path) -> ImageInfo:
        """Send one image file from this computer to the server."""
        file = Path(path)
        with file.open("rb") as handle:
            data = self._k.request(
                "POST", f"/projects/{project_id}/images", files={"file": (file.name, handle)}
            )
        return ImageInfo.from_api(data)

    def connect_folder(self, project_id: str, folder: str | Path) -> dict[str, Any]:
        """Read every image in a folder on the *server's* computer, in place. Waits until done."""
        made = self._k.request(
            "POST", f"/projects/{project_id}/folders", json={"path": str(folder)}
        )
        result: dict[str, Any] = self._k.wait_for(made["job"]["id"])["result"]
        return result


class _Annotations(_Part):
    def list(self, image_id: str) -> list[Annotation]:
        return [
            Annotation.from_api(a)
            for a in self._k.request("GET", f"/images/{image_id}/annotations")
        ]

    def add_boxes(
        self, image_id: str, boxes: Sequence[tuple[str, float, float, float, float]]
    ) -> int:
        """Add boxes as `(class_id, x, y, w, h)`, each a fraction of the image (0 to 1).

        Returns how many were saved. Ids are made here, so calling this again after a dropped
        connection would add the boxes twice: check with `list` first if unsure.
        """
        import uuid

        ops = [
            {
                "op": "create",
                "id": str(uuid.uuid4()),
                "type": "box",
                "class_id": class_id,
                "geometry": {"x": x, "y": y, "w": w, "h": h},
            }
            for class_id, x, y, w, h in boxes
        ]
        return self.batch(image_id, ops)

    def batch(self, image_id: str, ops: Sequence[dict[str, Any]]) -> int:
        """Send create, update and delete operations. Raises if the server refuses any."""
        result = self._k.request(
            "POST", f"/images/{image_id}/annotations:batch", json={"ops": list(ops)}
        )
        problems = [r for r in result["results"] if r["status"] != "ok"]
        if problems:
            first = problems[0]
            raise KatibError(
                422, first["status"], first.get("error") or "An operation was refused."
            )
        return len(result["results"])
