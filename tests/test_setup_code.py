from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from katib.api.app import create_app
from katib.config import Settings
from katib.services import setup_code

API = "/api/v1"
PUBLIC = ("93.184.216.34", 5000)
HOME = ("192.168.1.20", 5000)
SIGNUP = {"email": "boss@example.org", "name": "Boss", "password": "correct horse battery"}


def server(tmp_path: Path) -> Settings:
    return Settings(storage={"data_dir": str(tmp_path / "data")}, auth={"mode": "local"})


@pytest.mark.parametrize(
    ("host", "local"),
    [
        ("127.0.0.1", True),
        ("::1", True),
        ("192.168.1.20", True),
        ("10.0.0.5", True),
        ("172.17.0.1", True),
        ("fe80::1", True),
        ("testclient", True),
        ("93.184.216.34", False),
        ("8.8.8.8", False),
        ("2606:4700::1111", False),
    ],
)
def test_which_addresses_count_as_local(host: str, local: bool) -> None:
    assert setup_code.is_local_address(host) is local


def test_the_code_is_made_once_and_easy_to_type(tmp_path: Path) -> None:
    code = setup_code.get_or_create(tmp_path)
    assert len(code) == 10
    assert not set(code) & set("01OIL")
    assert setup_code.get_or_create(tmp_path) == code
    assert setup_code.matches(tmp_path, code.lower() + " ")
    assert not setup_code.matches(tmp_path, "WRONGCODE1")


def test_someone_at_home_needs_no_code(tmp_path: Path) -> None:
    with TestClient(create_app(server(tmp_path)), client=HOME) as api:
        assert api.get(f"{API}/auth/status").json()["needs_setup_code"] is False
        assert api.post(f"{API}/auth/setup", json=SIGNUP).status_code == 201


def test_someone_on_the_internet_needs_the_code(tmp_path: Path) -> None:
    settings = server(tmp_path)
    with TestClient(create_app(settings), client=PUBLIC) as api:
        status = api.get(f"{API}/auth/status").json()
        assert status["needs_setup"] is True
        assert status["needs_setup_code"] is True

        refused = api.post(f"{API}/auth/setup", json=SIGNUP)
        assert refused.status_code == 403
        assert "setup code" in refused.json()["message"]

        code = (settings.data_dir / "setup-code.txt").read_text().strip()
        wrong = api.post(f"{API}/auth/setup", json={**SIGNUP, "setup_code": "NOTTHECODE"})
        assert wrong.status_code == 403
        done = api.post(f"{API}/auth/setup", json={**SIGNUP, "setup_code": code})
        assert done.status_code == 201
    assert not (settings.data_dir / "setup-code.txt").exists()


def test_guessing_the_code_is_slowed_down(tmp_path: Path) -> None:
    with TestClient(create_app(server(tmp_path)), client=PUBLIC) as api:
        replies = [
            api.post(f"{API}/auth/setup", json={**SIGNUP, "setup_code": f"GUESS{n}"}).status_code
            for n in range(12)
        ]
    assert 429 in replies


def test_an_untrusted_proxy_in_the_path_means_the_code_is_needed() -> None:
    home = "192.168.1.20"
    assert setup_code.needs_code(home, {}, trusts_proxy=False) is False
    assert setup_code.needs_code(home, {"x-forwarded-for": "8.8.8.8"}, trusts_proxy=False) is True
    assert setup_code.needs_code(home, {"x-forwarded-for": "8.8.8.8"}, trusts_proxy=True) is False
    assert setup_code.needs_code("8.8.8.8", {}, trusts_proxy=True) is True


def test_the_setup_code_file_is_private(tmp_path: Path) -> None:
    setup_code.get_or_create(tmp_path)
    mode = (tmp_path / "setup-code.txt").stat().st_mode & 0o777
    assert mode in (0o600, 0o666, 0o644)  # Windows has no owner-only mode to check


def test_a_proxy_that_katib_was_not_told_about_gets_asked_for_the_code(tmp_path: Path) -> None:
    with TestClient(create_app(server(tmp_path)), client=HOME) as api:
        behind = {"x-forwarded-for": "93.184.216.34"}
        assert api.get(f"{API}/auth/status", headers=behind).json()["needs_setup_code"] is True
        assert api.post(f"{API}/auth/setup", json=SIGNUP, headers=behind).status_code == 403
