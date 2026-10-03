"""The factory reset service, on its own: what it counts, what it deletes, and what it admits
to leaving behind when something could not be removed.
"""

from pathlib import Path

import pytest

from katib.services import reset


def test_preview_counts_without_deleting_anything(tmp_path: Path) -> None:
    (tmp_path / "katib.db").write_bytes(b"x" * 10)
    (tmp_path / "uploads").mkdir()
    (tmp_path / "uploads" / "a.png").write_bytes(b"y" * 5)

    report = reset.preview(tmp_path)

    assert report.files == 2
    assert report.bytes == 15
    assert report.failed == []
    assert (tmp_path / "katib.db").exists()


def test_factory_reset_removes_everything_it_can(tmp_path: Path) -> None:
    (tmp_path / "katib.db").write_bytes(b"x")
    (tmp_path / "uploads").mkdir()
    (tmp_path / "uploads" / "a.png").write_bytes(b"y")

    report = reset.factory_reset(tmp_path)

    assert report.files == 2
    assert report.failed == []
    assert list(tmp_path.iterdir()) == []


def test_a_file_that_cannot_be_deleted_is_reported_not_hidden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A locked file used to be swallowed by ignore_errors=True: the reset looked clean even
    when it was not. This pins the fix without depending on real OS-level file locking."""
    locked = tmp_path / "katib.db"
    locked.write_bytes(b"x")
    (tmp_path / "settings.json").write_bytes(b"{}")

    real_unlink = Path.unlink

    def fussy_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self.name == "katib.db":
            raise PermissionError("file is in use")
        real_unlink(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "unlink", fussy_unlink)

    report = reset.factory_reset(tmp_path)

    assert report.failed == [str(locked)]
    assert locked.exists()
    assert not (tmp_path / "settings.json").exists()
    # What was left is written down, so the fresh server can say so after the restart.
    assert reset.leftovers(tmp_path) == [str(locked)]
    reset.forget_leftovers(tmp_path)
    assert reset.leftovers(tmp_path) == []


def test_the_running_servers_own_files_are_left_alone(tmp_path: Path) -> None:
    # The lock and the log are held open by the server doing the reset; on Windows they cannot be
    # deleted, and they are not data anyway.
    (tmp_path / "server.lock").write_bytes(b"")
    (tmp_path / "server.json").write_text("{}")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "server.log").write_text("hello")
    (tmp_path / "katib.db").write_bytes(b"x")

    report = reset.factory_reset(tmp_path)

    assert report.files == 1
    assert report.failed == []
    assert sorted(p.name for p in tmp_path.iterdir()) == ["logs", "server.json", "server.lock"]
