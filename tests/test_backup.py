import os
import sqlite3
import time
import zipfile
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from katib import restart
from katib.api.app import create_app
from katib.cli import app as cli
from katib.config import Settings
from katib.services import backup
from katib.services.errors import InvalidInput


def make_data(root: Path) -> str:
    """A data folder with a small database and one upload. Returns the database address."""
    (root / "uploads" / "p").mkdir(parents=True)
    (root / "uploads" / "p" / "a.png").write_bytes(b"picture")
    db = root / "katib.db"
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("CREATE TABLE t (n INTEGER)")
        conn.execute("INSERT INTO t VALUES (7)")
        conn.commit()
    return f"sqlite:///{db.as_posix()}"


def test_a_backup_restores_into_an_empty_folder(tmp_path: Path) -> None:
    url = make_data(tmp_path / "data")
    zip_path = tmp_path / "backup.zip"
    made = backup.create(tmp_path / "data", url, zip_path)
    assert made.files == 2

    target = tmp_path / "fresh"
    backup.restore(zip_path, target)
    assert (target / "uploads" / "p" / "a.png").read_bytes() == b"picture"
    with closing(sqlite3.connect(target / "katib.db")) as conn:
        assert conn.execute("SELECT n FROM t").fetchone() == (7,)


def test_restoring_over_a_database_needs_permission_and_keeps_the_old_one(tmp_path: Path) -> None:
    url = make_data(tmp_path / "data")
    zip_path = tmp_path / "backup.zip"
    backup.create(tmp_path / "data", url, zip_path)
    with pytest.raises(InvalidInput, match="already has a database"):
        backup.restore(zip_path, tmp_path / "data")
    backup.restore(zip_path, tmp_path / "data", replace=True)
    assert (tmp_path / "data" / "katib.db.before-restore").is_file()


def test_a_zip_that_writes_outside_the_folder_is_refused(tmp_path: Path) -> None:
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("katib.db", "x")
        z.writestr("backup.json", "{}")
        z.writestr("../escaped.txt", "no")
    with pytest.raises(InvalidInput, match="outside"):
        backup.restore(evil, tmp_path / "data")
    assert not (tmp_path / "escaped.txt").exists()


def test_something_that_is_not_a_backup_is_refused(tmp_path: Path) -> None:
    junk = tmp_path / "notes.zip"
    with zipfile.ZipFile(junk, "w") as z:
        z.writestr("hello.txt", "hi")
    with pytest.raises(InvalidInput, match="does not look like"):
        backup.restore(junk, tmp_path / "data")


def test_postgres_cannot_be_backed_up_this_way(tmp_path: Path) -> None:
    with pytest.raises(InvalidInput, match="pg_dump"):
        backup.create(tmp_path, "postgresql://u:p@h/db", tmp_path / "x.zip")


def test_the_restore_command_puts_a_backup_back(tmp_path: Path) -> None:
    url = make_data(tmp_path / "data")
    zip_path = tmp_path / "backup.zip"
    backup.create(tmp_path / "data", url, zip_path)
    (tmp_path / "katib.toml").write_text(
        f'[storage]\ndata_dir = "{(tmp_path / "fresh").as_posix()}"\n'
    )
    result = CliRunner().invoke(
        cli, ["restore", str(zip_path), "--config", str(tmp_path / "katib.toml")]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "fresh" / "katib.db").is_file()


def test_restart_runs_the_same_command_again(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["katib", "serve", "--port", "9000"])
    monkeypatch.setattr("sys.frozen", False, raising=False)
    assert restart.command()[1:] == ["katib", "serve", "--port", "9000"]
    monkeypatch.setattr("sys.frozen", True, raising=False)
    assert restart.command()[1:] == ["serve", "--port", "9000"]


def test_the_restart_button_starts_a_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(restart, "restart_soon", lambda: calls.append("restart"))
    with TestClient(create_app(Settings(storage={"data_dir": str(tmp_path)}))) as api:
        assert api.post("/api/v1/settings/restart").status_code == 202
        api.app.state.can_restart = False  # type: ignore[attr-defined]
        blocked = api.post("/api/v1/settings/restart")
        assert blocked.status_code == 422
    assert calls == ["restart"]


def test_old_backups_are_deleted_and_new_ones_kept(tmp_path: Path) -> None:
    old, fresh = tmp_path / "katib-backup-old.zip", tmp_path / "katib-backup-new.zip"
    other = tmp_path / "yolo-export.zip"
    for file in (old, fresh, other):
        file.write_bytes(b"x")
    long_ago = time.time() - 3 * 24 * 3600
    os.utime(old, (long_ago, long_ago))
    os.utime(other, (long_ago, long_ago))
    assert backup.remove_old_backups(tmp_path) == 1
    assert not old.exists()
    assert fresh.exists()
    assert other.exists()  # only backups are touched
