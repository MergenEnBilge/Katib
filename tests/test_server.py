import json
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from typer.testing import CliRunner

from katib.cli import app as cli
from katib.config import Settings
from katib.server import instance, run
from katib.server.run import AlreadyRunning, ManagedServer, free_port


def settings_for(data: Path) -> Settings:
    # Port 0 asks the system for any free port, so tests never fight over 8420.
    return Settings(storage={"data_dir": str(data)}, server={"port": 0})


def test_only_one_holder_of_a_data_folder(tmp_path: Path) -> None:
    first, second = instance.InstanceLock(tmp_path), instance.InstanceLock(tmp_path)
    assert first.acquire()
    assert not second.acquire()
    assert not instance.lock_is_free(tmp_path)
    first.release()
    assert instance.lock_is_free(tmp_path)
    assert second.acquire()
    second.release()


def test_the_lock_goes_with_a_process_that_dies(tmp_path: Path) -> None:
    # The holder dies with os._exit, so nothing of its own lets go of the lock: only the operating
    # system can. (Killing it from here would not do: on Windows a virtualenv's python.exe is a
    # launcher, and killing that leaves the real interpreter running.)
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import os, sys; from pathlib import Path; from katib.server.instance import "
            f"InstanceLock; lock = InstanceLock(Path({str(tmp_path)!r})); "
            "print(lock.acquire(), flush=True); sys.stdin.read(); os._exit(1)",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert holder.stdout is not None and holder.stdin is not None
    assert holder.stdout.readline().strip() == "True"
    assert not instance.lock_is_free(tmp_path)
    holder.stdin.close()
    holder.wait(timeout=30)
    assert instance.lock_is_free(tmp_path)


def test_a_left_over_server_file_is_not_a_running_server(tmp_path: Path) -> None:
    info = instance.ServerInfo(
        pid=1, url="http://127.0.0.1:1", host="127.0.0.1", port=1, version="0", token="t"
    )
    instance.write_info(tmp_path, info)
    assert instance.read_info(tmp_path) == info
    # Nobody holds the folder, so whatever wrote that file is gone.
    assert instance.find_running(tmp_path) is None


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("127.0.0.1", "http://127.0.0.1:8420"),
        ("localhost", "http://127.0.0.1:8420"),
        ("0.0.0.0", "http://127.0.0.1:8420"),  # noqa: S104
        ("192.168.1.20", "http://192.168.1.20:8420"),
    ],
)
def test_programs_here_reach_the_server_where_it_answers(host: str, expected: str) -> None:
    assert instance.local_url(host, 8420) == expected


def test_free_port_prefers_the_configured_port() -> None:
    port = free_port("127.0.0.1", 0)
    assert free_port("127.0.0.1", port) == port


def test_free_port_falls_back_when_the_configured_port_is_taken() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
        busy.bind(("127.0.0.1", 0))
        taken = busy.getsockname()[1]
        assert free_port("127.0.0.1", taken) != taken


@pytest.mark.slow
def test_a_server_announces_itself_and_stops_when_asked(tmp_path: Path) -> None:
    server = ManagedServer(settings_for(tmp_path), any_port=True)
    info = server.start()
    try:
        found = instance.find_running(tmp_path)
        assert found == info
        written = json.loads((tmp_path / instance.INFO_NAME).read_text(encoding="utf-8"))
        assert written["token"] == server.token
        assert instance.stop(info, tmp_path)
    finally:
        server.stop()
        server.wait()
    assert instance.find_running(tmp_path) is None
    assert not (tmp_path / instance.INFO_NAME).exists()
    assert instance.lock_is_free(tmp_path)


@pytest.mark.slow
def test_stopping_needs_the_token(tmp_path: Path) -> None:
    server = ManagedServer(settings_for(tmp_path), any_port=True)
    info = server.start()
    try:
        request = urllib.request.Request(
            f"{info.url}/api/v1/server:stop",
            method="POST",
            headers={instance.CONTROL_HEADER: "a guess"},
        )
        with pytest.raises(urllib.error.HTTPError) as refused:
            urllib.request.urlopen(request, timeout=5)
        assert refused.value.code == 403
        assert instance.find_running(tmp_path) is not None
    finally:
        server.stop()
        server.wait()


@pytest.mark.slow
def test_a_second_server_for_the_same_folder_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run, "LOCK_WAIT_SECONDS", 0.2)
    first = ManagedServer(settings_for(tmp_path), any_port=True)
    info = first.start()
    try:
        with pytest.raises(AlreadyRunning) as err:
            ManagedServer(settings_for(tmp_path), any_port=True).start()
        assert err.value.url == info.url
    finally:
        first.stop()
        first.wait()


def test_a_server_without_a_control_has_nothing_to_stop(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from katib.api.app import create_app

    with TestClient(create_app(settings_for(tmp_path))) as client:
        assert client.post("/api/v1/server:stop").status_code == 404


@pytest.mark.slow
def test_restore_waits_for_the_server_to_stop(tmp_path: Path) -> None:
    data = tmp_path / "data"
    (tmp_path / "katib.toml").write_text(
        f'[storage]\ndata_dir = "{data.as_posix()}"\n[server]\nport = 0\n'
    )
    server = ManagedServer(settings_for(data), any_port=True)
    server.start()
    try:
        result = CliRunner().invoke(
            cli,
            ["restore", str(tmp_path / "missing.zip"), "--config", str(tmp_path / "katib.toml")],
        )
        assert result.exit_code != 0
        assert "katib stop" in result.output
    finally:
        server.stop()
        server.wait()


@pytest.mark.slow
def test_status_and_stop_from_the_command_line(tmp_path: Path) -> None:
    data = tmp_path / "data"
    config = tmp_path / "katib.toml"
    config.write_text(f'[storage]\ndata_dir = "{data.as_posix()}"\n[server]\nport = 0\n')
    runner = CliRunner()
    assert runner.invoke(cli, ["status", "--config", str(config)]).exit_code == 1

    server = ManagedServer(settings_for(data), any_port=True)
    info = server.start()
    try:
        shown = runner.invoke(cli, ["status", "--config", str(config)])
        assert shown.exit_code == 0 and info.url in shown.output
        stopped = runner.invoke(cli, ["stop", "--config", str(config)])
        assert stopped.exit_code == 0, stopped.output
        server.wait_until_stopped()
    finally:
        server.stop()
        server.wait()
    assert instance.lock_is_free(data)
