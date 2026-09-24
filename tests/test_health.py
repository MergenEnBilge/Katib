from fastapi.testclient import TestClient


def test_health_reports_ok(client: TestClient) -> None:
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["version"]


def test_unknown_api_path_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/nope").status_code == 404
