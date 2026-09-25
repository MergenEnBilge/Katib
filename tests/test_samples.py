from fastapi.testclient import TestClient
from PIL import Image as PILImage

API = "/api/v1"


def test_the_practice_project_has_pictures_classes_and_one_labeled_example(
    client: TestClient,
) -> None:
    made = client.post(f"{API}/samples")
    assert made.status_code == 201
    project = made.json()
    assert project["name"] == "Try Katib"
    assert project["image_count"] == 6
    assert set(project["annotation_types"]) == {"box", "polygon", "tag", "text"}

    classes = client.get(f"{API}/projects/{project['id']}/classes").json()
    assert [c["name"] for c in classes] == ["ball", "crate"]

    images = client.get(f"{API}/projects/{project['id']}/images").json()["items"]
    first = client.get(f"{API}/images/{images[0]['id']}/annotations").json()
    kinds = sorted(a["type"] for a in first)
    assert kinds.count("text") == 1
    assert kinds.count("box") >= 4
    for other in images[1:]:
        assert client.get(f"{API}/images/{other['id']}/annotations").json() == []


def test_each_labeled_box_sits_on_something_that_is_not_grass(client: TestClient) -> None:
    project = client.post(f"{API}/samples").json()
    image = client.get(f"{API}/projects/{project['id']}/images").json()["items"][0]
    boxes = [
        a["geometry"]
        for a in client.get(f"{API}/images/{image['id']}/annotations").json()
        if a["type"] == "box"
    ]
    file = client.get(f"{API}/images/{image['id']}/file")
    import io

    picture = PILImage.open(io.BytesIO(file.content)).convert("RGB")
    grass = (96, 160, 88)
    for box in boxes:
        centre = (
            int((box["x"] + box["w"] / 2) * picture.width),
            int((box["y"] + box["h"] / 2) * picture.height),
        )
        assert picture.getpixel(centre) != grass


def test_asking_again_makes_another_copy_with_its_own_name(client: TestClient) -> None:
    names = [client.post(f"{API}/samples").json()["name"] for _ in range(3)]
    assert names == ["Try Katib", "Try Katib 2", "Try Katib 3"]
