"""A small practice project, so someone can learn Katib without bringing their own pictures.

The pictures are drawn on the spot: balls and crates on a field. That keeps the download small,
needs no image files in the package, and means the practice labels are always right.
"""

import io
import random
import uuid
from dataclasses import dataclass

from PIL import Image as PILImage
from PIL import ImageDraw
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from katib.db.ids import new_id
from katib.db.models import Annotation, Project
from katib.services import classes, projects
from katib.services.images import StorageContext, import_upload

WIDTH, HEIGHT = 800, 600
PICTURES = 6
BASE_NAME = "Try Katib"
BALL_COLORS = ("#d94f4f", "#e0a83a", "#4f8fd9", "#8a5cc7")


@dataclass(frozen=True)
class Item:
    kind: str  # "ball" or "crate"
    x: int
    y: int
    size: int

    def box(self) -> dict[str, float]:
        """The box around it, as fractions of the picture."""
        half = self.size
        left, top = max(self.x - half, 0), max(self.y - half, 0)
        right, bottom = min(self.x + half, WIDTH), min(self.y + half, HEIGHT)
        return {
            "x": left / WIDTH,
            "y": top / HEIGHT,
            "w": (right - left) / WIDTH,
            "h": (bottom - top) / HEIGHT,
        }


def _scene(seed: int) -> list[Item]:
    """A few balls and crates that do not overlap."""
    rng = random.Random(seed)
    items: list[Item] = []
    for _ in range(200):
        if len(items) == 4 + seed % 2:
            break
        item = Item(
            rng.choice(("ball", "crate")),
            rng.randint(110, WIDTH - 110),
            rng.randint(250, HEIGHT - 90),
            rng.randint(42, 70),
        )
        if all(abs(item.x - o.x) > item.size + o.size + 12 for o in items):
            items.append(item)
    return items


def _paint(items: list[Item], seed: int) -> bytes:
    rng = random.Random(seed + 100)
    picture = PILImage.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(picture)
    for row in range(HEIGHT // 2):
        shade = 150 + int(80 * row / (HEIGHT / 2))
        draw.line([(0, row), (WIDTH, row)], fill=(shade - 60, shade - 20, 255))
    draw.rectangle([0, HEIGHT // 2, WIDTH, HEIGHT], fill=(96, 160, 88))
    for _ in range(14):
        x, y = rng.randint(0, WIDTH), rng.randint(HEIGHT // 2, HEIGHT)
        draw.line([(x, y), (x + 4, y - 12)], fill=(74, 132, 70), width=3)
    for item in sorted(items, key=lambda i: i.y):
        left, top, right, bottom = (
            item.x - item.size,
            item.y - item.size,
            item.x + item.size,
            item.y + item.size,
        )
        if item.kind == "ball":
            color = BALL_COLORS[(item.x + seed) % len(BALL_COLORS)]
            draw.ellipse([left, top, right, bottom], fill=color, outline=(40, 40, 40), width=3)
            gleam = item.size // 3
            draw.ellipse(
                [left + gleam, top + gleam, left + gleam * 2, top + gleam * 2], fill=(255, 255, 255)
            )
        else:
            draw.rectangle(
                [left, top, right, bottom], fill=(176, 122, 68), outline=(84, 56, 30), width=4
            )
            for third in (1, 2):
                y = top + (bottom - top) * third // 3
                draw.line([(left, y), (right, y)], fill=(120, 80, 44), width=3)
    out = io.BytesIO()
    picture.save(out, "PNG")
    return out.getvalue()


def _unused_name(session: Session) -> str:
    """Try Katib, or Try Katib 2 when someone has done this before."""
    name, number = BASE_NAME, 2
    while session.scalar(select(Project.id).where(func.lower(Project.name) == name.lower())):
        name = f"{BASE_NAME} {number}"
        number += 1
    return name


def create_sample(session: Session, ctx: StorageContext, user_id: uuid.UUID | None) -> Project:
    """Make the practice project. Its first picture is already labeled, to show what done looks
    like, and the others are left for the person to try."""
    project = projects.create_project(
        session, _unused_name(session), ["box", "polygon", "tag", "text"], created_by=user_id
    )
    ball = classes.create_class(session, project.id, "ball")
    crate = classes.create_class(session, project.id, "crate")
    by_kind = {"ball": ball.id, "crate": crate.id}
    for number in range(PICTURES):
        items = _scene(number)
        image = import_upload(
            session,
            project.id,
            f"practice-{number + 1}.png",
            io.BytesIO(_paint(items, number)),
            ctx,
        )
        if number != 0:
            continue
        for item in items:
            session.add(
                Annotation(
                    id=new_id(),
                    image_id=image.id,
                    class_id=by_kind[item.kind],
                    type="box",
                    geometry=item.box(),
                    created_by=user_id,
                )
            )
        balls = sum(1 for i in items if i.kind == "ball")
        session.add(
            Annotation(
                id=new_id(),
                image_id=image.id,
                type="text",
                geometry={
                    "text": f"{balls} balls and {len(items) - balls} crates on a grassy field."
                },
                created_by=user_id,
            )
        )
    session.flush()
    return project
