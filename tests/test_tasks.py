import threading
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from katib.db.base import utcnow
from katib.db.migrate import upgrade_to_head
from katib.db.models import Image, User
from katib.db.session import make_engine, make_session_factory
from katib.services import access, auth, discussion, projects, tasks
from katib.services.errors import Forbidden, InvalidInput
from katib.services.tasks import ImageLocked

PASSWORD = "correct horse battery"


class Team:
    def __init__(self, session: Session, images: int = 5) -> None:
        self.session = session
        self.admin = auth.create_user(
            session, "admin@example.com", "Admin", PASSWORD, is_admin=True
        )
        self.project = projects.create_project(session, "P", created_by=self.admin.id)
        self.ann1 = self.member("ann1", "annotator")
        self.ann2 = self.member("ann2", "annotator")
        self.reviewer = self.member("rev", "reviewer")
        self.viewer = self.member("view", "viewer")
        self.images: list[Image] = []
        for i in range(images):
            img = Image(
                project_id=self.project.id, filename=f"{i}.jpg", storage_key=f"k{i}",
                width=10, height=10, sha256=str(i), position=i,
            )  # fmt: skip
            session.add(img)
            self.images.append(img)
        session.flush()

    def member(self, name: str, role: str) -> User:
        user = auth.create_user(self.session, f"{name}@example.com", name, PASSWORD)
        access.add_member(self.session, self.project.id, user.id, role)
        return user


@pytest.fixture
def team(session: Session) -> Team:
    return Team(session)


def test_next_hands_out_the_first_todo_and_then_the_same_one_until_done(team: Team) -> None:
    first = tasks.next_image(team.session, team.ann1, team.project.id)
    assert first is not None and first.filename == "0.jpg"
    assert (first.status, first.assignee_id) == ("in_progress", team.ann1.id)
    again = tasks.next_image(team.session, team.ann1, team.project.id)
    assert again is not None and again.id == first.id

    other = tasks.next_image(team.session, team.ann2, team.project.id)
    assert other is not None and other.filename == "1.jpg"

    tasks.transition(team.session, team.ann1, first.id, "done")
    following = tasks.next_image(team.session, team.ann1, team.project.id)
    assert following is not None and following.filename == "2.jpg"


def test_next_returns_none_when_the_queue_is_empty(session: Session) -> None:
    team = Team(session, images=1)
    assert tasks.next_image(session, team.ann1, team.project.id) is not None
    assert tasks.next_image(session, team.ann2, team.project.id) is None


def test_assigned_images_are_reserved_for_their_person(team: Team) -> None:
    ids = [i.id for i in team.images]
    assert tasks.assign(team.session, team.project.id, ids[:2], team.ann2.id) == 2
    mine = tasks.next_image(team.session, team.ann1, team.project.id)
    assert mine is not None and mine.filename == "2.jpg"
    theirs = tasks.next_image(team.session, team.ann2, team.project.id)
    assert theirs is not None and theirs.filename == "0.jpg"
    with pytest.raises(InvalidInput):
        tasks.assign(team.session, team.project.id, ids[:1], uuid.uuid4())
    outsider = auth.create_user(team.session, "o@example.com", "O", PASSWORD)
    with pytest.raises(InvalidInput, match="not in this project"):
        tasks.assign(team.session, team.project.id, ids[:1], outsider.id)


def test_two_people_never_get_the_same_image(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'race.db').as_posix()}"
    upgrade_to_head(url)
    engine = make_engine(url)
    factory = make_session_factory(engine)
    with factory() as s:
        team = Team(s, images=24)
        s.commit()
        project_id = team.project.id
        users = [team.ann1.id, team.ann2.id]

    got: dict[uuid.UUID, list[uuid.UUID]] = {u: [] for u in users}
    errors: list[BaseException] = []

    def worker(user_id: uuid.UUID) -> None:
        try:
            for _ in range(12):
                with factory() as s:
                    user = s.get(User, user_id)
                    assert user is not None
                    image = tasks.next_image(s, user, project_id)
                    if image is not None:
                        got[user_id].append(image.id)
                        tasks.transition(s, user, image.id, "done")
                    s.commit()
        except BaseException as err:  # noqa: BLE001 - surfaced by the assertion below
            errors.append(err)

    threads = [threading.Thread(target=worker, args=(u,)) for u in users]
    [t.start() for t in threads]
    [t.join() for t in threads]
    engine.dispose()
    assert errors == []
    a, b = got[users[0]], got[users[1]]
    assert set(a).isdisjoint(b)
    assert len(a) + len(b) == 24


def test_locks_are_taken_renewed_expire_and_can_be_taken_over(team: Team) -> None:
    image = team.images[0]
    now = utcnow()
    held = tasks.lock_image(team.session, team.ann1, image.id, now)
    assert held.locked_by == team.ann1.id
    tasks.lock_image(team.session, team.ann1, image.id, now + timedelta(seconds=15))

    with pytest.raises(ImageLocked) as err:
        tasks.lock_image(team.session, team.ann2, image.id, now + timedelta(seconds=20))
    assert err.value.details["name"] == "ann1" and "ann1 is editing" in err.value.message
    assert tasks.lock_state(team.session, held, now + timedelta(seconds=20)) is not None

    late = now + timedelta(seconds=15 + tasks.LOCK_SECONDS + 1)
    assert tasks.lock_state(team.session, held, late) is None
    assert tasks.lock_image(team.session, team.ann2, image.id, late).locked_by == team.ann2.id

    tasks.unlock_image(team.session, team.ann1, image.id)  # not the holder, so no effect
    team.session.expire_all()
    assert team.session.get(Image, image.id).locked_by == team.ann2.id  # type: ignore[union-attr]
    tasks.unlock_image(team.session, team.ann2, image.id)
    team.session.expire_all()
    assert team.session.get(Image, image.id).locked_by is None  # type: ignore[union-attr]

    tasks.lock_image(team.session, team.ann1, image.id)
    assert tasks.take_over(team.session, image.id, team.admin).locked_by == team.admin.id


def test_annotators_finish_and_reopen_but_cannot_review(team: Team) -> None:
    image = team.images[0]
    done = tasks.transition(team.session, team.ann1, image.id, "done")
    assert done.status == "done" and done.assignee_id == team.ann1.id
    with pytest.raises(InvalidInput, match="Review is off"):
        tasks.transition(team.session, team.reviewer, image.id, "approved")
    reopened = tasks.transition(team.session, team.ann1, image.id, "in_progress")
    assert reopened.status == "in_progress"
    with pytest.raises(Forbidden):
        tasks.transition(team.session, team.viewer, image.id, "done")


def test_review_flow(team: Team) -> None:
    tasks.set_review(team.session, team.project.id, True)
    image = team.images[0]
    with pytest.raises(InvalidInput, match="marked as done"):
        tasks.transition(team.session, team.reviewer, image.id, "approved")
    tasks.transition(team.session, team.ann1, image.id, "done")
    with pytest.raises(Forbidden):
        tasks.transition(team.session, team.ann1, image.id, "approved")

    rejected = tasks.transition(team.session, team.reviewer, image.id, "rejected")
    assert (rejected.status, rejected.reviewer_id) == ("rejected", team.reviewer.id)
    fixed = tasks.transition(team.session, team.ann1, image.id, "done")
    assert fixed.status == "done"
    approved = tasks.transition(team.session, team.reviewer, image.id, "approved")
    assert approved.status == "approved"
    with pytest.raises(Forbidden, match="reviewer"):
        tasks.transition(team.session, team.ann1, image.id, "in_progress")
    assert (
        tasks.transition(team.session, team.reviewer, image.id, "in_progress").status
        == "in_progress"
    )


def test_a_rejected_image_comes_back_to_its_annotator(team: Team) -> None:
    tasks.set_review(team.session, team.project.id, True)
    first = tasks.next_image(team.session, team.ann1, team.project.id)
    assert first is not None
    tasks.transition(team.session, team.ann1, first.id, "done")
    tasks.transition(team.session, team.reviewer, first.id, "rejected")
    back = tasks.next_image(team.session, team.ann1, team.project.id)
    assert back is not None and back.id == first.id and back.status == "rejected"


def test_comments_and_activity(team: Team) -> None:
    image = team.images[0]
    comment = discussion.add_comment(
        team.session, team.reviewer, image.id, "  Box is too loose  ", x=0.2, y=0.4
    )
    assert comment.body == "Box is too loose"
    rows = discussion.list_comments(team.session, image.id)
    assert [(r.author, r.comment.body) for r in rows] == [("rev", "Box is too loose")]
    assert discussion.set_resolved(team.session, comment.id, True).resolved_at is not None
    assert discussion.set_resolved(team.session, comment.id, False).resolved_at is None
    for bad in ("", "   "):
        with pytest.raises(InvalidInput):
            discussion.add_comment(team.session, team.reviewer, image.id, bad)
    with pytest.raises(InvalidInput, match="inside the image"):
        discussion.add_comment(team.session, team.reviewer, image.id, "hi", x=2.0)
    with pytest.raises(InvalidInput, match="not on this image"):
        discussion.add_comment(
            team.session, team.reviewer, image.id, "hi", annotation_id=uuid.uuid4()
        )

    discussion.log(team.session, team.project.id, team.ann1, "marked_done", {"n": 1})
    feed = discussion.recent(team.session, team.project.id)
    assert [(name, a.verb) for a, name in feed] == [("ann1", "marked_done"), ("rev", "commented")]
