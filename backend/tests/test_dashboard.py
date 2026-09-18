from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import utcnow
from app.models import Board, BoardMember, Card, User
from app.services.auth import create_access_token

DASHBOARD_KEYS = {"board_id", "total", "by_column", "overdue", "done", "progress_percent"}
COLUMN_COUNT_KEYS = {"column_id", "name", "position", "count"}


def make_user(session: Session, email: str) -> User:
    user = User(email=email, password_hash="not-a-real-hash", display_name="x")
    session.add(user)
    session.commit()
    return user


def headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def add_card(session: Session, board_id: int, column_id: int, due: datetime | None = None) -> Card:
    card = Card(board_id=board_id, column_id=column_id, title="t", position=0, due_date=due)
    session.add(card)
    session.commit()
    return card


YESTERDAY = utcnow() - timedelta(days=1)
TOMORROW = utcnow() + timedelta(days=1)


@pytest.fixture
def owner(session: Session) -> User:
    return make_user(session, "owner@example.com")


@pytest.fixture
def outsider(session: Session) -> User:
    return make_user(session, "outsider@example.com")


class Fixture:
    def __init__(self, client: TestClient, session: Session, owner: User):
        self.id = client.post("/boards", json={"name": "Roadmap"}, headers=headers(owner)).json()["id"]
        self.todo, self.doing, self.done = [
            c.id for c in sorted(session.get(Board, self.id).columns, key=lambda c: c.position)
        ]


@pytest.fixture
def board(client, session, owner) -> Fixture:
    return Fixture(client, session, owner)


@pytest.fixture
def dashboard(client: TestClient, owner: User):
    def get(board_id: int, as_user: User = owner):
        return client.get(f"/boards/{board_id}/dashboard", headers=headers(as_user))

    return get


# --- zero cards ------------------------------------------------------------------


def test_empty_board(dashboard, board):
    response = dashboard(board.id)

    assert response.status_code == 200
    body = response.json()
    assert body.keys() == DASHBOARD_KEYS
    assert body["board_id"] == board.id
    assert body["total"] == 0
    assert body["overdue"] == 0
    assert body["done"] == 0
    assert body["progress_percent"] == 0
    assert body["by_column"] == [
        {"column_id": board.todo, "name": "To Do", "position": 0, "count": 0},
        {"column_id": board.doing, "name": "In Progress", "position": 1, "count": 0},
        {"column_id": board.done, "name": "Done", "position": 2, "count": 0},
    ]


# --- each metric -----------------------------------------------------------------


def test_total_and_counts_by_column(dashboard, board, session):
    add_card(session, board.id, board.todo)
    add_card(session, board.id, board.todo)
    add_card(session, board.id, board.done)

    body = dashboard(board.id).json()

    assert body["total"] == 3
    assert [(c["name"], c["count"]) for c in body["by_column"]] == [
        ("To Do", 2), ("In Progress", 0), ("Done", 1)
    ]
    assert all(c.keys() == COLUMN_COUNT_KEYS for c in body["by_column"])


def test_by_column_follows_column_position(dashboard, board, session, client, owner):
    add_card(session, board.id, board.done)
    client.patch(f"/columns/{board.done}", json={"position": 0}, headers=headers(owner))

    body = dashboard(board.id).json()

    assert [(c["name"], c["position"], c["count"]) for c in body["by_column"]] == [
        ("Done", 0, 1), ("To Do", 1, 0), ("In Progress", 2, 0)
    ]


def test_overdue_counts_past_due_cards_outside_done(dashboard, board, session):
    add_card(session, board.id, board.todo, due=YESTERDAY)       # overdue
    add_card(session, board.id, board.doing, due=YESTERDAY)      # overdue
    add_card(session, board.id, board.done, due=YESTERDAY)       # done: not overdue
    add_card(session, board.id, board.todo, due=TOMORROW)        # not yet due
    add_card(session, board.id, board.todo)                      # no due date

    assert dashboard(board.id).json()["overdue"] == 2


def test_due_exactly_now_is_not_overdue(dashboard, board, session, monkeypatch):
    fixed = datetime(2026, 6, 1, 12, 0, 0)
    add_card(session, board.id, board.todo, due=fixed)
    add_card(session, board.id, board.todo, due=fixed - timedelta(seconds=1))
    import app.routers.dashboard as module
    monkeypatch.setattr(module, "utcnow", lambda: fixed)

    assert dashboard(board.id).json()["overdue"] == 1


def test_progress_percent(dashboard, board, session):
    add_card(session, board.id, board.todo)
    add_card(session, board.id, board.doing)
    add_card(session, board.id, board.done)

    body = dashboard(board.id).json()

    assert body["done"] == 1
    assert body["progress_percent"] == 33.3


def test_progress_is_100_when_everything_is_done(dashboard, board, session):
    add_card(session, board.id, board.done)
    add_card(session, board.id, board.done)

    assert dashboard(board.id).json()["progress_percent"] == 100


# --- how "Done" is identified ---------------------------------------------------------


def test_done_is_matched_by_name_case_and_whitespace_insensitive(dashboard, board, session, client, owner):
    client.patch(f"/columns/{board.done}", json={"name": "  DONE "}, headers=headers(owner))
    add_card(session, board.id, board.done, due=YESTERDAY)

    body = dashboard(board.id).json()

    assert (body["done"], body["overdue"], body["progress_percent"]) == (1, 0, 100)


def test_renamed_done_column_no_longer_counts(dashboard, board, session, client, owner):
    client.patch(f"/columns/{board.done}", json={"name": "Shipped"}, headers=headers(owner))
    add_card(session, board.id, board.done, due=YESTERDAY)

    body = dashboard(board.id).json()

    assert (body["done"], body["overdue"], body["progress_percent"]) == (0, 1, 0)


def test_every_column_named_done_counts(dashboard, board, session, client, owner):
    extra = client.post(f"/boards/{board.id}/columns", json={"name": "done"}, headers=headers(owner)).json()["id"]
    add_card(session, board.id, board.done)
    add_card(session, board.id, extra)
    add_card(session, board.id, board.todo)

    body = dashboard(board.id).json()

    assert body["done"] == 2
    assert body["progress_percent"] == 66.7


# --- scoping and access ---------------------------------------------------------------


def test_metrics_are_scoped_to_the_board(dashboard, board, session, client, owner):
    other = Fixture(client, session, owner)
    add_card(session, other.id, other.todo, due=YESTERDAY)
    add_card(session, other.id, other.done)

    body = dashboard(board.id).json()

    assert (body["total"], body["overdue"], body["done"]) == (0, 0, 0)


def test_member_can_view(dashboard, board, session):
    member = make_user(session, "member@example.com")
    session.add(BoardMember(board_id=board.id, user_id=member.id, role="member"))
    session.commit()

    assert dashboard(board.id, as_user=member).status_code == 200


def test_non_member_is_404(dashboard, board, outsider):
    assert dashboard(board.id, as_user=outsider).status_code == 404


def test_unknown_board_is_404(dashboard):
    assert dashboard(999).status_code == 404


def test_requires_token(client, board):
    assert client.get(f"/boards/{board.id}/dashboard").status_code == 401
