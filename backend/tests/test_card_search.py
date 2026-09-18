import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Board, BoardMember, User
from app.services.auth import create_access_token


def make_user(session: Session, email: str) -> User:
    user = User(email=email, password_hash="not-a-real-hash", display_name="x")
    session.add(user)
    session.commit()
    return user


def headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest.fixture
def owner(session: Session) -> User:
    return make_user(session, "owner@example.com")


@pytest.fixture
def member(session: Session) -> User:
    return make_user(session, "member@example.com")


class Fixture:
    """Five cards spread over columns, priorities and assignees."""

    def __init__(self, client: TestClient, session: Session, owner: User, member: User):
        self.id = client.post("/boards", json={"name": "Roadmap"}, headers=headers(owner)).json()["id"]
        session.add(BoardMember(board_id=self.id, user_id=member.id, role="member"))
        session.commit()
        self.todo, self.doing, self.done = [
            c.id for c in sorted(session.get(Board, self.id).columns, key=lambda c: c.position)
        ]
        cards = [
            dict(title="Fix login bug", description="", column_id=self.todo, priority="high", assignee_id=owner.id),
            dict(title="Write docs", description="Explain the LOGIN flow", column_id=self.todo, priority="low"),
            dict(title="Refactor", description="100% coverage", column_id=self.doing, priority="high", assignee_id=member.id),
            dict(title="Ship it", description="", column_id=self.done, priority="medium", assignee_id=owner.id),
            dict(title="snake_case", description="", column_id=self.done, priority="low"),
        ]
        for card in cards:
            assert client.post(f"/boards/{self.id}/cards", json=card, headers=headers(owner)).status_code == 201


@pytest.fixture
def board(client, session, owner, member) -> Fixture:
    return Fixture(client, session, owner, member)


@pytest.fixture
def search(client: TestClient, owner: User, board: Fixture):
    def run(**params) -> list[str]:
        response = client.get(f"/boards/{board.id}/cards", params=params, headers=headers(owner))
        assert response.status_code == 200, response.text
        return [c["title"] for c in response.json()]

    return run


ALL = ["Fix login bug", "Write docs", "Refactor", "Ship it", "snake_case"]


def test_no_filters_returns_everything(search):
    assert search() == ALL


# --- q ---------------------------------------------------------------------------


def test_q_matches_title(search):
    assert search(q="fix") == ["Fix login bug"]


def test_q_matches_description(search):
    assert search(q="flow") == ["Write docs"]


def test_q_is_case_insensitive_on_both_fields(search):
    assert search(q="LOGIN") == ["Fix login bug", "Write docs"]
    assert search(q="login") == ["Fix login bug", "Write docs"]


def test_q_matches_substrings_and_is_trimmed(search):
    assert search(q="  docs ") == ["Write docs"]


def test_q_no_match(search):
    assert search(q="zzz") == []


@pytest.mark.parametrize("q", ["", "   "])
def test_blank_q_is_ignored(search, q):
    assert search(q=q) == ALL


def test_q_treats_like_wildcards_literally(search):
    assert search(q="100%") == ["Refactor"]
    assert search(q="%") == ["Refactor"]
    assert search(q="e_c") == ["snake_case"]
    assert search(q="_") == ["snake_case"]


# --- each filter -----------------------------------------------------------------


def test_filter_by_column(search, board):
    assert search(column_id=board.todo) == ["Fix login bug", "Write docs"]
    assert search(column_id=board.done) == ["Ship it", "snake_case"]


def test_filter_by_column_of_another_board_is_empty(search, board, client, owner, session):
    other = client.post("/boards", json={"name": "Other"}, headers=headers(owner)).json()
    assert search(column_id=other["columns"][0]["id"]) == []


def test_filter_by_priority(search):
    assert search(priority="high") == ["Fix login bug", "Refactor"]
    assert search(priority="medium") == ["Ship it"]
    assert search(priority="low") == ["Write docs", "snake_case"]


def test_invalid_priority_is_422(client, board, owner):
    response = client.get(f"/boards/{board.id}/cards", params={"priority": "urgent"}, headers=headers(owner))
    assert response.status_code == 422


def test_invalid_ids_are_422(client, board, owner):
    for params in ({"column_id": "abc"}, {"assignee_id": "abc"}):
        assert client.get(f"/boards/{board.id}/cards", params=params, headers=headers(owner)).status_code == 422


def test_filter_by_assignee(search, owner, member):
    assert search(assignee_id=owner.id) == ["Fix login bug", "Ship it"]
    assert search(assignee_id=member.id) == ["Refactor"]
    assert search(assignee_id=999) == []


# --- combinations ------------------------------------------------------------------


def test_filters_combine_with_and(search, board, owner):
    assert search(q="login", column_id=board.todo) == ["Fix login bug", "Write docs"]
    assert search(q="login", priority="high") == ["Fix login bug"]
    assert search(column_id=board.todo, priority="high", assignee_id=owner.id) == ["Fix login bug"]
    assert search(column_id=board.todo, assignee_id=owner.id, priority="low") == []
    assert search(q="i", column_id=board.done, priority="medium", assignee_id=owner.id) == ["Ship it"]


def test_results_keep_board_order(search, board, client, owner):
    client.patch(f"/columns/{board.done}", json={"position": 0}, headers=headers(owner))
    assert search(priority="low") == ["snake_case", "Write docs"]


def test_unknown_query_params_are_ignored(search):
    assert search(label_id=1, due_before="2030-01-01") == ALL


def test_non_member_is_404(client, board, session):
    outsider = make_user(session, "outsider@example.com")
    response = client.get(f"/boards/{board.id}/cards", params={"q": "x"}, headers=headers(outsider))
    assert response.status_code == 404
