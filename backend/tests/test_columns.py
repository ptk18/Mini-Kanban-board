import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Board, BoardMember, Card, Column, User
from app.services.auth import create_access_token


def make_user(session: Session, email: str) -> User:
    user = User(email=email, password_hash="not-a-real-hash", display_name=email.split("@")[0])
    session.add(user)
    session.commit()
    return user


def headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def db_columns(session: Session, board_id: int) -> list[tuple[str, int]]:
    session.expire_all()
    rows = session.scalars(
        select(Column).where(Column.board_id == board_id).order_by(Column.position)
    )
    return [(c.name, c.position) for c in rows]


@pytest.fixture
def owner(session: Session) -> User:
    return make_user(session, "owner@example.com")


@pytest.fixture
def member(session: Session) -> User:
    return make_user(session, "member@example.com")


@pytest.fixture
def outsider(session: Session) -> User:
    return make_user(session, "outsider@example.com")


@pytest.fixture
def board(client: TestClient, session: Session, owner: User, member: User) -> Board:
    """A board with the three default columns, ``member`` added."""
    board_id = client.post("/boards", json={"name": "Roadmap"}, headers=headers(owner)).json()["id"]
    session.add(BoardMember(board_id=board_id, user_id=member.id, role="member"))
    session.commit()
    return session.get(Board, board_id)


@pytest.fixture
def api(client: TestClient, owner: User):
    class Api:
        def create(self, board_id: int, name: str, as_user: User = owner):
            return client.post(
                f"/boards/{board_id}/columns", json={"name": name}, headers=headers(as_user)
            )

        def patch(self, column_id: int, as_user: User = owner, **body):
            return client.patch(f"/columns/{column_id}", json=body, headers=headers(as_user))

        def delete(self, column_id: int, as_user: User = owner):
            return client.delete(f"/columns/{column_id}", headers=headers(as_user))

    return Api()


def column_ids(session: Session, board: Board) -> list[int]:
    session.expire_all()
    return [c.id for c in sorted(board.columns, key=lambda c: c.position)]


# --- create --------------------------------------------------------------------


def test_create_appends_after_defaults(api, board, session):
    response = api.create(board.id, "  Review  ")

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Review"
    assert body["position"] == 3
    assert body["board_id"] == board.id
    assert body["created_at"].endswith(("Z", "+00:00"))
    assert db_columns(session, board.id) == [
        ("To Do", 0), ("In Progress", 1), ("Done", 2), ("Review", 3)
    ]


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_create_rejects_bad_name(api, board, name):
    assert api.create(board.id, name).status_code == 422


def test_create_on_unknown_board_is_404(api):
    assert api.create(999, "x").status_code == 404


# --- rename --------------------------------------------------------------------


def test_rename(api, board, session):
    todo = column_ids(session, board)[0]

    response = api.patch(todo, name=" Backlog ")

    assert response.status_code == 200
    assert response.json()["name"] == "Backlog"
    assert response.json()["position"] == 0


def test_patch_with_no_fields_is_422(api, board, session):
    assert api.patch(column_ids(session, board)[0]).status_code == 422


@pytest.mark.parametrize("body", [{"name": ""}, {"position": -1}])
def test_patch_rejects_invalid_values(api, board, session, body):
    assert api.patch(column_ids(session, board)[0], **body).status_code == 422


def test_patch_unknown_column_is_404(api):
    assert api.patch(999, name="x").status_code == 404


# --- reorder -------------------------------------------------------------------


def test_reorder_moves_column_to_the_end(api, board, session):
    todo, progress, done = column_ids(session, board)

    response = api.patch(todo, position=2)

    assert response.status_code == 200
    assert response.json()["position"] == 2
    assert db_columns(session, board.id) == [("In Progress", 0), ("Done", 1), ("To Do", 2)]


def test_reorder_moves_column_to_the_front(api, board, session):
    todo, progress, done = column_ids(session, board)

    api.patch(done, position=0)

    assert db_columns(session, board.id) == [("Done", 0), ("To Do", 1), ("In Progress", 2)]


def test_rename_and_reorder_together(api, board, session):
    todo, progress, done = column_ids(session, board)

    body = api.patch(progress, name="Doing", position=0).json()

    assert (body["name"], body["position"]) == ("Doing", 0)
    assert db_columns(session, board.id) == [("Doing", 0), ("To Do", 1), ("Done", 2)]


def test_reorder_past_end_is_422_and_changes_nothing(api, board, session):
    todo = column_ids(session, board)[0]

    response = api.patch(todo, position=3)

    assert response.status_code == 422
    assert response.json()["detail"] == "position must be between 0 and 2"
    assert db_columns(session, board.id) == [("To Do", 0), ("In Progress", 1), ("Done", 2)]


def test_reorder_does_not_touch_other_boards(api, board, session, client, owner):
    other_id = client.post("/boards", json={"name": "Other"}, headers=headers(owner)).json()["id"]
    todo = column_ids(session, board)[0]

    api.patch(todo, position=2)

    assert db_columns(session, other_id) == [("To Do", 0), ("In Progress", 1), ("Done", 2)]


# --- delete --------------------------------------------------------------------


def test_delete_empty_column_closes_the_gap(api, board, session):
    todo, progress, done = column_ids(session, board)

    response = api.delete(progress)

    assert response.status_code == 204
    assert response.content == b""
    assert session.get(Column, progress) is None
    assert db_columns(session, board.id) == [("To Do", 0), ("Done", 1)]


def test_delete_column_with_cards_is_409(api, board, session):
    todo = column_ids(session, board)[0]
    session.add(Card(board_id=board.id, column_id=todo, title="t", position=0))
    session.commit()

    response = api.delete(todo)

    assert response.status_code == 409
    assert response.json() == {"detail": "Column still holds 1 card(s); move them first"}
    assert session.get(Column, todo) is not None
    assert db_columns(session, board.id) == [("To Do", 0), ("In Progress", 1), ("Done", 2)]


def test_delete_unknown_column_is_404(api):
    assert api.delete(999).status_code == 404


def test_delete_all_columns_then_create_starts_at_zero(api, board, session):
    for column_id in column_ids(session, board):
        assert api.delete(column_id).status_code == 204

    assert api.create(board.id, "Fresh").json()["position"] == 0


# --- membership ----------------------------------------------------------------


def test_member_can_manage_columns(api, board, member, session):
    created = api.create(board.id, "Review", as_user=member)
    assert created.status_code == 201
    column_id = created.json()["id"]

    assert api.patch(column_id, as_user=member, name="QA", position=0).status_code == 200
    assert api.delete(column_id, as_user=member).status_code == 204


def test_non_member_is_rejected_on_every_endpoint(api, board, outsider, session):
    todo = column_ids(session, board)[0]

    assert api.create(board.id, "x", as_user=outsider).status_code == 404
    assert api.patch(todo, as_user=outsider, name="x").status_code == 404
    assert api.delete(todo, as_user=outsider).status_code == 404
    assert db_columns(session, board.id) == [("To Do", 0), ("In Progress", 1), ("Done", 2)]
