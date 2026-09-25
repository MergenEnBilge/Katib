import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image as PILImage

API = "/api/v1"

EXAMPLES: dict[str, dict[str, object]] = {
    "obb": {"cx": 0.5, "cy": 0.5, "w": 0.3, "h": 0.1, "angle": 0.5},
    "keypoints": {"points": [{"x": 0.2, "y": 0.2, "v": 2}, {"x": 0.4, "y": 0.5, "v": 1}]},
    "mask": {"rle": "0,4,12", "size": [4, 4]},
    "tag": {},
}


def test_every_new_type_can_be_saved_when_the_project_uses_it(
    client: TestClient, tmp_path: Path
) -> None:
    project = client.post(
        f"{API}/projects", json={"name": "Shapes", "annotation_types": ["box", *EXAMPLES]}
    ).json()
    picture = tmp_path / "library" / "a.png"
    picture.parent.mkdir()
    PILImage.new("RGB", (40, 20), "red").save(picture)
    uploaded = client.post(
        f"{API}/projects/{project['id']}/images",
        files={"file": ("a.png", picture.read_bytes(), "image/png")},
    )
    image_id = uploaded.json()["id"]
    cls = client.post(f"{API}/projects/{project['id']}/classes", json={"name": "thing"}).json()

    ops = [
        {
            "op": "create",
            "id": str(uuid.uuid4()),
            "type": name,
            "class_id": cls["id"],
            "geometry": g,
        }
        for name, g in EXAMPLES.items()
    ]
    res = client.post(f"{API}/images/{image_id}/annotations:batch", json={"ops": ops})

    assert [r["status"] for r in res.json()["results"]] == ["ok"] * len(EXAMPLES)
    health = client.get(f"{API}/projects/{project['id']}/health")
    assert health.status_code == 200


def test_a_project_must_opt_in_to_a_type(client: TestClient, tmp_path: Path) -> None:
    project = client.post(f"{API}/projects", json={"name": "Boxes only"}).json()
    picture = tmp_path / "a.png"
    PILImage.new("RGB", (8, 8), "red").save(picture)
    image_id = client.post(
        f"{API}/projects/{project['id']}/images",
        files={"file": ("a.png", picture.read_bytes(), "image/png")},
    ).json()["id"]

    res = client.post(
        f"{API}/images/{image_id}/annotations:batch",
        json={"ops": [{"op": "create", "id": str(uuid.uuid4()), "type": "tag", "geometry": {}}]},
    )

    result = res.json()["results"][0]
    assert result["status"] == "invalid"
    assert "does not use tag" in result["error"]
