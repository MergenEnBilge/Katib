import io
import uuid
from pathlib import Path

import pytest
from PIL import Image as PILImage
from sqlalchemy import select
from sqlalchemy.orm import Session

from katib.db.models import Image
from katib.services import images, projects
from katib.services.errors import ImportNotAllowed, InvalidInput
from katib.services.images import StorageContext
from katib.storage.local import LocalStorage


def make_png(path: Path, size: tuple[int, int] = (40, 20), color: str = "red") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    PILImage.new("RGB", size, color).save(path)


@pytest.fixture
def ctx(tmp_path: Path) -> StorageContext:
    lib = tmp_path / "library"
    lib.mkdir()
    return StorageContext(
        uploads=LocalStorage(tmp_path / "data" / "uploads"),
        thumbs=LocalStorage(tmp_path / "data" / "thumbs"),
        allowed_roots=[lib],
        max_upload_bytes=50_000,
    )


@pytest.fixture
def pid(session: Session) -> uuid.UUID:
    return projects.create_project(session, "P").id


def test_folder_import_indexes_in_place(
    session: Session, pid: uuid.UUID, ctx: StorageContext
) -> None:
    lib = ctx.allowed_roots[0]
    make_png(lib / "b.png", color="red")
    make_png(lib / "sub" / "a.png", (10, 30), "blue")
    (lib / "notes.txt").write_text("skip me")
    before = (lib / "b.png").read_bytes()

    report = images.import_folder(session, pid, str(lib), ctx)

    assert report.added == 2
    rows = list(session.scalars(select(Image).order_by(Image.position)))
    assert [r.filename for r in rows] == ["b.png", "a.png"]
    assert [(r.width, r.height) for r in rows] == [(40, 20), (10, 30)]
    assert rows[0].storage_key.startswith("file:")
    assert (lib / "b.png").read_bytes() == before
    assert all(ctx.thumbs.exists(f"{r.id}.jpg") for r in rows)


def test_duplicates_are_skipped_with_a_reason(
    session: Session, pid: uuid.UUID, ctx: StorageContext
) -> None:
    lib = ctx.allowed_roots[0]
    make_png(lib / "one.png")
    make_png(lib / "two.png")
    report = images.import_folder(session, pid, str(lib), ctx)
    assert report.added == 1
    assert "duplicate of one.png" in report.skipped[0].reason
    again = images.import_folder(session, pid, str(lib), ctx)
    assert again.added == 0


def test_unreadable_files_are_reported(
    session: Session, pid: uuid.UUID, ctx: StorageContext
) -> None:
    lib = ctx.allowed_roots[0]
    (lib / "broken.png").write_bytes(b"not an image")
    report = images.import_folder(session, pid, str(lib), ctx)
    assert report.added == 0
    assert "not a readable image" in report.skipped[0].reason


def test_folder_outside_roots_is_refused(
    session: Session, pid: uuid.UUID, ctx: StorageContext, tmp_path: Path
) -> None:
    other = tmp_path / "elsewhere"
    make_png(other / "x.png")
    with pytest.raises(ImportNotAllowed):
        images.import_folder(session, pid, str(other), ctx)


def test_dotdot_cannot_escape_the_root(
    session: Session, pid: uuid.UUID, ctx: StorageContext, tmp_path: Path
) -> None:
    make_png(tmp_path / "x.png")
    sneaky = str(ctx.allowed_roots[0] / "..")
    with pytest.raises(ImportNotAllowed):
        images.import_folder(session, pid, sneaky, ctx)


def test_no_roots_means_folder_import_is_off(
    session: Session, pid: uuid.UUID, ctx: StorageContext
) -> None:
    off = StorageContext(ctx.uploads, ctx.thumbs, [], ctx.max_upload_bytes)
    with pytest.raises(ImportNotAllowed, match="off"):
        images.import_folder(session, pid, ".", off)


def test_upload_uses_generated_key_not_filename(
    session: Session, pid: uuid.UUID, ctx: StorageContext
) -> None:
    buf = io.BytesIO()
    PILImage.new("RGB", (8, 8), "green").save(buf, "PNG")
    buf.seek(0)
    img = images.import_upload(session, pid, "../../evil.png", buf, ctx)
    assert img.filename == "evil.png"
    assert ".." not in img.storage_key
    assert ctx.uploads.exists(img.storage_key)


def test_upload_rejects_wrong_type_and_big_files(
    session: Session, pid: uuid.UUID, ctx: StorageContext
) -> None:
    with pytest.raises(InvalidInput, match="supported"):
        images.import_upload(session, pid, "a.exe", io.BytesIO(b"x"), ctx)
    with pytest.raises(InvalidInput, match="MB|up to"):
        images.import_upload(session, pid, "a.png", io.BytesIO(b"0" * 60_000), ctx)
    with pytest.raises(InvalidInput, match="readable"):
        images.import_upload(session, pid, "a.png", io.BytesIO(b"junk"), ctx)


def test_image_path_recheck_for_referenced_files(
    session: Session, pid: uuid.UUID, ctx: StorageContext
) -> None:
    lib = ctx.allowed_roots[0]
    make_png(lib / "a.png")
    images.import_folder(session, pid, str(lib), ctx)
    img = session.scalars(select(Image)).one()
    assert images.image_path(img, ctx) == (lib / "a.png").resolve()
    shrunk = StorageContext(ctx.uploads, ctx.thumbs, [lib / "other"], ctx.max_upload_bytes)
    with pytest.raises(Exception, match="allowed"):
        images.image_path(img, shrunk)


def test_list_paginates_and_filters(session: Session, pid: uuid.UUID, ctx: StorageContext) -> None:
    lib = ctx.allowed_roots[0]
    for i in range(5):
        make_png(lib / f"img{i}.png", (10 + i, 10))
    images.import_folder(session, pid, str(lib), ctx)
    first = images.list_images(session, pid, limit=2)
    assert [r.image.filename for r in first.rows] == ["img0.png", "img1.png"]
    second = images.list_images(session, pid, limit=2, after=first.next)
    assert [r.image.filename for r in second.rows] == ["img2.png", "img3.png"]
    last = images.list_images(session, pid, limit=2, after=second.next)
    assert [r.image.filename for r in last.rows] == ["img4.png"]
    assert last.next is None
    assert len(images.list_images(session, pid, q="IMG3").rows) == 1
    assert images.list_images(session, pid, status="done").rows == []
    assert len(images.list_images(session, pid, has_annotations=False).rows) == 5
