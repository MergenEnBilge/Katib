"""Time the operations that have to stay fast (ARCHITECTURE.md section 19).

It builds a project full of made-up images and shapes in a throwaway database, then times each
operation. Run it with `uv run python scripts/bench.py`. With `--check` it exits with an error
when an operation is slower than its budget, which is how CI catches a slowdown.

Budgets are the targets in the architecture document with room to spare, because shared CI
machines are slower and noisier than a laptop. They are scaled to the size of the dataset built
here, not to the 1M shapes the targets mention.
"""

import argparse
import json
import statistics
import sys
import tempfile
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image as PILImage
from sqlalchemy import insert

from katib.api.app import create_app
from katib.config import Settings
from katib.core.dataset import ExportOptions
from katib.db.base import utcnow
from katib.db.ids import new_id
from katib.db.migrate import upgrade_to_head
from katib.db.models import Annotation, Class, Image, Project
from katib.db.session import make_engine, make_session_factory
from katib.services import class_ops, exchange, images
from katib.storage.local import LocalStorage

API = "/api/v1"

# Seconds. The comment says which target in the architecture document each one guards.
BUDGETS = {
    "list one page of images": 0.30,  # opening a big project
    "open an image (its shapes)": 0.20,  # switching image
    "rename a class": 0.20,  # under 50 ms
    "save 50 edits": 0.40,  # under 100 ms
    "merge two classes": 3.0,  # about 2 s for 1M shapes, so much less here
    "dataset health report": 12.0,
    "export as YOLO": 30.0,
    "import 200 images": 20.0,  # under 60 s per 1,000
}


def seed(settings: Settings, image_count: int, per_image: int) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """Fill the database directly. Going through the API would take longer than the benchmark."""
    upgrade_to_head(settings.database_url)
    engine = make_engine(settings.database_url)
    now = utcnow()
    project_id = new_id()
    class_ids = [new_id() for _ in range(6)]
    with make_session_factory(engine)() as s:
        s.add(
            Project(
                id=project_id,
                name="Bench",
                slug="bench",
                settings={"annotation_types": ["box", "polygon"], "review_enabled": False},
            )
        )
        s.flush()
        for i, class_id in enumerate(class_ids):
            s.add(
                Class(
                    id=class_id,
                    project_id=project_id,
                    name=f"class {i}",
                    color="#4c8df6",
                    position=i,
                )
            )
        s.flush()
        image_ids = [new_id() for _ in range(image_count)]
        s.execute(
            insert(Image),
            [
                {
                    "id": image_id,
                    "project_id": project_id,
                    "filename": f"img{n:06d}.jpg",
                    "storage_key": f"file:/nowhere/img{n:06d}.jpg",
                    "width": 1280,
                    "height": 720,
                    "sha256": f"{n:064x}",
                    "phash": f"{n:032x}",
                    "status": "todo",
                    "position": n,
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                }
                for n, image_id in enumerate(image_ids)
            ],
        )
        rows: list[dict[str, object]] = []
        for n, image_id in enumerate(image_ids):
            for k in range(per_image):
                rows.append(
                    {
                        "id": new_id(),
                        "image_id": image_id,
                        "class_id": class_ids[(n + k) % len(class_ids)],
                        "type": "box",
                        "geometry": {
                            "x": 0.05 + (k % 10) * 0.08,
                            "y": 0.05 + (k // 10 % 10) * 0.08,
                            "w": 0.06,
                            "h": 0.06,
                        },
                        "attrs": {},
                        "source": "manual",
                        "version": 1,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
            if len(rows) >= 20_000:
                s.execute(insert(Annotation), rows)
                rows = []
        if rows:
            s.execute(insert(Annotation), rows)
        s.commit()
    engine.dispose()
    return project_id, class_ids


def timed(action: Callable[[], object], repeat: int = 1) -> float:
    """Median seconds over `repeat` runs."""
    runs: list[float] = []
    for _ in range(repeat):
        start = time.perf_counter()
        action()
        runs.append(time.perf_counter() - start)
    return statistics.median(runs)


def measure(image_count: int, per_image: int) -> dict[str, float]:
    results: dict[str, float] = {}
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        settings = Settings(storage={"data_dir": str(root / "data")})
        (root / "data").mkdir()
        project_id, class_ids = seed(settings, image_count, per_image)

        library = root / "library"
        library.mkdir()
        for n in range(200):
            PILImage.new("RGB", (640, 480), (n % 256, (n * 7) % 256, (n * 13) % 256)).save(
                library / f"new{n:04d}.jpg"
            )

        with TestClient(create_app(settings)) as api:
            first = api.get(f"{API}/projects/{project_id}/images", params={"limit": 1}).json()
            image_id = first["items"][0]["id"]
            results["list one page of images"] = timed(
                lambda: api.get(f"{API}/projects/{project_id}/images", params={"limit": 100}), 5
            )
            results["open an image (its shapes)"] = timed(
                lambda: api.get(f"{API}/images/{image_id}/annotations"), 5
            )
            counter = iter(range(1_000_000))
            results["rename a class"] = timed(
                lambda: api.patch(
                    f"{API}/classes/{class_ids[0]}", json={"name": f"renamed {next(counter)}"}
                ),
                5,
            )

            def save_fifty() -> None:
                ops = [
                    {
                        "op": "create",
                        "id": str(uuid.uuid4()),
                        "type": "box",
                        "class_id": str(class_ids[1]),
                        "geometry": {"x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1},
                    }
                    for _ in range(50)
                ]
                api.post(f"{API}/images/{image_id}/annotations:batch", json={"ops": ops})

            results["save 50 edits"] = timed(save_fifty, 5)
            results["dataset health report"] = timed(
                lambda: api.get(f"{API}/projects/{project_id}/health")
            )

            factory = api.app.state.session_factory  # type: ignore[attr-defined]
            operations = LocalStorage(root / "data" / "operations")

            def merge() -> None:
                with factory() as s:
                    class_ops.merge_classes(s, operations, class_ids[2], class_ids[3])
                    s.commit()

            results["merge two classes"] = timed(merge)

            ctx = api.app.state.storage  # type: ignore[attr-defined]

            def export() -> None:
                with factory() as s:
                    exchange.export_dataset(
                        s, project_id, "yolo-detect", root / "export", ctx, ExportOptions()
                    )

            results["export as YOLO"] = timed(export)

            def bring_in() -> None:
                ctx.allowed_roots.append(library)
                with factory() as s:
                    images.import_folder(s, project_id, str(library), ctx)

            results["import 200 images"] = timed(bring_in)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=int, default=3000, help="images to seed")
    parser.add_argument("--shapes-per-image", type=int, default=30)
    parser.add_argument("--check", action="store_true", help="fail when a budget is exceeded")
    parser.add_argument("--json", type=Path, help="also write the results to this file")
    args = parser.parse_args()

    total = args.images * args.shapes_per_image
    print(f"Seeding {args.images:,} images and {total:,} shapes...", flush=True)
    results = measure(args.images, args.shapes_per_image)

    slow: list[str] = []
    print(f"\n{'operation':<32}{'seconds':>10}{'budget':>10}")
    for name, seconds in results.items():
        budget = BUDGETS[name]
        flag = "  too slow" if seconds > budget else ""
        print(f"{name:<32}{seconds:>10.3f}{budget:>10.2f}{flag}")
        if seconds > budget:
            slow.append(name)
    if args.json:
        args.json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    if args.check and slow:
        print(f"\nOver budget: {', '.join(slow)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
