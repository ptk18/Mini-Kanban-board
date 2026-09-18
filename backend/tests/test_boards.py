import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Board, BoardMember, Card, Column, User
from app.services.auth import create_access_token

BOARD_KEYS = {"id", "name", "owner_id", "role", "created_at", "updated_at"}
COLUMN_KEYS = {"id", "board_id", "name", "position", "created_at"}


def make_user(session: Session, email: str) -> User:
    user = User(email=email, password_hash="not-a-real-hash", display_name=email.split("@")[0])
    session.add(user)
    session.commit()
    return user


def headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


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
def api(client: TestClient, owner: User):
    class Api:
        def create(self, name: str = "Roadmap", as_user: User = owner):
            return client.post("/boards", json={"name": name}, headers=headers(as_user))

        def list(self, as_user: User = owner):
            return client.get("/boards", headers=headers(as_user))

        def get(self, board_id: int, as_user: User = owner):
            return client.get(f"/boards/{board_id}", headers=headers(as_user))

        def rename(self, board_id: int, name: str, as_user: User = owner):
            return client.patch(f"/boards/{board_id}", json={"name": name}, headers=headers(as_user))

        def delete(self, board_id: int, as_user: User = owner):
            return client.delete(f"/boards/{board_id}", headers=headers(as_user))

    return Api()


@pytest.fixture
def board_id(api, session: Session, member: User) -> int:
    """A board owned by ``owner`` with ``member`` added."""
    board_id = api.create().json()["id"]
    session.add(BoardMember(board_id=board_id, user_id=member.id, role="member"))
    session.commit()
    return board_id


# --- create --------------------------------------------------------------------


def test_create_board_returns_detail_with_default_columns(api, owner, session):
    response = api.create("  Roadmap  ")

    assert response.status_code == 201
    body = response.json()
    assert body.keys() == BOARD_KEYS | {"columns"}
    assert body["name"] == "Roadmap"
    assert body["owner_id"] == owner.id
    assert body["role"] == "owner"
    assert body["created_at"].endswith(("Z", "+00:00"))
    assert [(c["name"], c["position"]) for c in body["columns"]] == [
        ("To Do", 0),
        ("In Progress", 1),
        ("Done", 2),
    ]
    assert all(c.keys() == COLUMN_KEYS and c["board_id"] == body["id"] for c in body["columns"])


def test_create_board_adds_owner_member_row(api, owner, session):
    board_id = api.create().json()["id"]

    membership = session.scalar(select(BoardMember).where(BoardMember.board_id == board_id))
    assert (membership.user_id, membership.role) == (owner.id, "owner")
    assert count(session, BoardMember) == 1
    assert count(session, Column) == 3


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_create_rejects_bad_name(api, name):
    assert api.create(name).status_code == 422


def test_create_requires_token(client):
    assert client.post("/boards", json={"name": "x"}).status_code == 401


# --- list ----------------------------------------------------------------------


def test_list_returns_only_boards_the_user_belongs_to(api, owner, member, outsider, session):
    mine = api.create("Mine").json()["id"]
    shared = api.create("Shared").json()["id"]
    api.create("Theirs", as_user=outsider)
    session.add(BoardMember(board_id=shared, user_id=member.id, role="member"))
    session.commit()

    assert [(b["name"], b["role"]) for b in api.list().json()] == [("Mine", "owner"), ("Shared", "owner")]
    assert [(b["name"], b["role"]) for b in api.list(as_user=member).json()] == [("Shared", "member")]
    assert [b["name"] for b in api.list(as_user=outsider).json()] == ["Theirs"]


def test_list_is_empty_for_a_user_with_no_boards(api, outsider):
    assert api.list(as_user=outsider).json() == []


def test_list_items_have_board_keys_and_no_columns(api):
    api.create()
    (item,) = api.list().json()
    assert item.keys() == BOARD_KEYS


# --- view / rename ---------------------------------------------------------------


def test_member_can_view_board_with_columns_in_order(api, board_id, member, session):
    board = session.get(Board, board_id)
    columns = sorted(board.columns, key=lambda c: c.position)
    columns[0].position, columns[2].position = 2, 0
    session.commit()

    response = api.get(board_id, as_user=member)

    assert response.status_code == 200
    assert response.json()["role"] == "member"
    assert [c["name"] for c in response.json()["columns"]] == ["Done", "In Progress", "To Do"]


def test_member_can_rename(api, board_id, member, session):
    response = api.rename(board_id, " Renamed ", as_user=member)

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"
    assert response.json().keys() == BOARD_KEYS
    session.expire_all()
    assert session.get(Board, board_id).name == "Renamed"


@pytest.mark.parametrize("name", ["", "x" * 101])
def test_rename_rejects_bad_name(api, board_id, name):
    assert api.rename(board_id, name).status_code == 422


def test_non_member_gets_404_on_view_rename_delete(api, board_id, outsider, session):
    assert api.get(board_id, as_user=outsider).status_code == 404
    assert api.rename(board_id, "x", as_user=outsider).status_code == 404
    assert api.delete(board_id, as_user=outsider).status_code == 404
    assert session.get(Board, board_id) is not None


def test_unknown_board_is_404(api):
    assert api.get(999).status_code == 404


# --- delete ----------------------------------------------------------------------


def test_member_cannot_delete(api, board_id, member, session):
    response = api.delete(board_id, as_user=member)

    assert response.status_code == 403
    assert response.json() == {"detail": "Only the board owner can do this"}
    assert session.get(Board, board_id) is not None


def test_owner_can_delete_and_everything_cascades(api, board_id, owner, session):
    column_id = session.get(Board, board_id).columns[0].id
    session.add(Card(board_id=board_id, column_id=column_id, title="t", position=0))
    session.commit()

    response = api.delete(board_id)

    assert response.status_code == 204
    assert response.content == b""
    session.expire_all()
    assert session.get(Board, board_id) is None
    assert count(session, BoardMember) == 0
    assert count(session, Column) == 0
    assert count(session, Card) == 0
    assert session.get(User, owner.id) is not None
    assert api.list().json() == []


def test_owner_without_member_row_still_owns(api, board_id, owner, session):
    session.execute(BoardMember.__table__.delete())
    session.commit()

    assert api.get(board_id).json()["role"] == "owner"
    assert api.delete(board_id).status_code == 204
