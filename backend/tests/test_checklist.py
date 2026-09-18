from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Board, BoardMember, Card, ChecklistItem, Column, User
from app.services.auth import create_access_token

ITEM_KEYS = {"id", "card_id", "content", "completed", "position"}
CARD_KEYS = {
    "id",
    "board_id",
    "column_id",
    "parent_card_id",
    "title",
    "description",
    "priority",
    "due_date",
    "assignee_id",
    "position",
    "created_at",
    "updated_at",
    "checklist_items",
}


def make_user(session: Session, email: str) -> User:
    user = User(email=email, password_hash="not-a-real-hash", display_name=email.split("@")[0])
    session.add(user)
    session.commit()
    return user


def make_board(session: Session, owner: User, *members: User) -> Board:
    board = Board(name="Roadmap", owner_id=owner.id)
    session.add(board)
    session.flush()
    session.add(BoardMember(board_id=board.id, user_id=owner.id, role="owner"))
    for member in members:
        session.add(BoardMember(board_id=board.id, user_id=member.id, role="member"))
    session.commit()
    return board


def make_card(session: Session, board: Board, title: str = "Write tests") -> Card:
    column = Column(board_id=board.id, name="Todo", position=0)
    session.add(column)
    session.flush()
    card = Card(board_id=board.id, column_id=column.id, title=title, position=0)
    session.add(card)
    session.commit()
    return card


def headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def db_positions(session: Session, card_id: int) -> list[tuple[str, int]]:
    """(content, position) pairs straight from the table, ordered by position."""
    session.expire_all()
    rows = session.scalars(
        select(ChecklistItem)
        .where(ChecklistItem.card_id == card_id)
        .order_by(ChecklistItem.position)
    )
    return [(item.content, item.position) for item in rows]


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
def card(session: Session, owner: User, member: User) -> Card:
    return make_card(session, make_board(session, owner, member))


@pytest.fixture
def api(client: TestClient, owner: User):
    """Checklist helpers acting as the board owner."""

    class Api:
        def add(self, card_id: int, content: str, as_user: User = owner):
            return client.post(
                f"/cards/{card_id}/checklist", json={"content": content}, headers=headers(as_user)
            )

        def patch(self, item_id: int, as_user: User = owner, **body):
            return client.patch(f"/checklist/{item_id}", json=body, headers=headers(as_user))

        def delete(self, item_id: int, as_user: User = owner):
            return client.delete(f"/checklist/{item_id}", headers=headers(as_user))

        def list(self, card_id: int, as_user: User = owner):
            return client.get(f"/cards/{card_id}/checklist", headers=headers(as_user))

        def card(self, card_id: int, as_user: User = owner):
            return client.get(f"/cards/{card_id}", headers=headers(as_user))

        def seed(self, card_id: int, *contents: str) -> list[int]:
            return [self.add(card_id, content).json()["id"] for content in contents]

    return Api()


# --- add ---------------------------------------------------------------------


def test_add_item_appends_at_end(api, card, session):
    first = api.add(card.id, "  Write the test  ")
    second = api.add(card.id, "Run it")

    assert first.status_code == 201
    assert first.json().keys() == ITEM_KEYS
    assert first.json() == {
        "id": first.json()["id"],
        "card_id": card.id,
        "content": "Write the test",
        "completed": False,
        "position": 0,
    }
    assert second.json()["position"] == 1
    assert db_positions(session, card.id) == [("Write the test", 0), ("Run it", 1)]


@pytest.mark.parametrize("content", ["", "   ", "x" * 501])
def test_add_rejects_bad_content(api, card, content):
    assert api.add(card.id, content).status_code == 422


def test_add_requires_token(client, card):
    response = client.post(f"/cards/{card.id}/checklist", json={"content": "x"})
    assert response.status_code == 401


def test_add_to_unknown_card_is_404(api):
    assert api.add(999, "x").status_code == 404


# --- edit / toggle -----------------------------------------------------------


def test_edit_content(api, card):
    (item_id,) = api.seed(card.id, "Old")

    response = api.patch(item_id, content=" New ")

    assert response.status_code == 200
    assert response.json()["content"] == "New"
    assert response.json()["completed"] is False


def test_toggle_completed_both_ways(api, card):
    (item_id,) = api.seed(card.id, "Task")

    assert api.patch(item_id, completed=True).json()["completed"] is True
    assert api.list(card.id).json()[0]["completed"] is True
    assert api.patch(item_id, completed=False).json()["completed"] is False


def test_edit_and_toggle_in_one_request(api, card):
    (item_id,) = api.seed(card.id, "Task")

    body = api.patch(item_id, content="Done task", completed=True).json()

    assert (body["content"], body["completed"]) == ("Done task", True)


def test_patch_with_no_fields_is_422(api, card):
    (item_id,) = api.seed(card.id, "Task")
    assert api.patch(item_id).status_code == 422


@pytest.mark.parametrize("body", [{"content": ""}, {"position": -1}, {"completed": "maybe"}])
def test_patch_rejects_invalid_values(api, card, body):
    (item_id,) = api.seed(card.id, "Task")
    assert api.patch(item_id, **body).status_code == 422


def test_patch_unknown_item_is_404(api):
    assert api.patch(999, content="x").status_code == 404


# --- reorder -----------------------------------------------------------------


def test_reorder_moves_item_down_and_keeps_positions_contiguous(api, card, session):
    a, b, c, d = api.seed(card.id, "a", "b", "c", "d")

    response = api.patch(a, position=2)

    assert response.status_code == 200
    assert response.json()["position"] == 2
    assert db_positions(session, card.id) == [("b", 0), ("c", 1), ("a", 2), ("d", 3)]


def test_reorder_moves_item_up(api, card, session):
    api.seed(card.id, "a", "b", "c")
    c = api.list(card.id).json()[2]["id"]

    api.patch(c, position=0)

    assert db_positions(session, card.id) == [("c", 0), ("a", 1), ("b", 2)]


def test_reorder_to_same_position_is_noop(api, card, session):
    a, b = api.seed(card.id, "a", "b")

    assert api.patch(b, position=1).status_code == 200
    assert db_positions(session, card.id) == [("a", 0), ("b", 1)]


def test_reorder_past_end_is_422(api, card, session):
    a, b = api.seed(card.id, "a", "b")

    response = api.patch(a, position=2)

    assert response.status_code == 422
    assert response.json()["detail"] == "position must be between 0 and 1"
    assert db_positions(session, card.id) == [("a", 0), ("b", 1)]


def test_reorder_does_not_touch_other_cards(api, card, session, owner):
    other = make_card(session, session.get(Board, card.board_id), title="Other")
    api.seed(other.id, "x", "y")
    a, b = api.seed(card.id, "a", "b")

    api.patch(b, position=0)

    assert db_positions(session, other.id) == [("x", 0), ("y", 1)]


# --- delete ------------------------------------------------------------------


def test_delete_removes_item_and_closes_the_gap(api, card, session):
    a, b, c = api.seed(card.id, "a", "b", "c")

    response = api.delete(b)

    assert response.status_code == 204
    assert response.content == b""
    assert session.get(ChecklistItem, b) is None
    assert db_positions(session, card.id) == [("a", 0), ("c", 1)]


def test_delete_unknown_item_is_404(api):
    assert api.delete(999).status_code == 404


def test_delete_then_add_reuses_the_freed_position(api, card):
    a, b = api.seed(card.id, "a", "b")
    api.delete(b)

    assert api.add(card.id, "c").json()["position"] == 1


# --- card detail and list -----------------------------------------------------


def test_card_detail_includes_checklist_in_position_order(api, card, session):
    a, b, c = api.seed(card.id, "a", "b", "c")
    api.patch(c, position=0)
    api.patch(a, completed=True)

    response = api.card(card.id)

    assert response.status_code == 200
    body = response.json()
    assert body.keys() == CARD_KEYS
    assert body["id"] == card.id
    assert body["title"] == "Write tests"
    assert body["due_date"] is None
    assert body["created_at"].endswith(("Z", "+00:00"))
    assert [(i["content"], i["position"], i["completed"]) for i in body["checklist_items"]] == [
        ("c", 0, False),
        ("a", 1, True),
        ("b", 2, False),
    ]


def test_card_detail_with_empty_checklist(api, card):
    assert api.card(card.id).json()["checklist_items"] == []


def test_list_endpoint_returns_items_in_order(api, card):
    a, b = api.seed(card.id, "a", "b")
    api.patch(b, position=0)

    assert [i["content"] for i in api.list(card.id).json()] == ["b", "a"]


def test_card_detail_due_date_is_serialised_as_utc(api, card, session):
    card.due_date = datetime(2026, 1, 2, 3, 4, 5)
    session.commit()

    assert api.card(card.id).json()["due_date"] == "2026-01-02T03:04:05Z"


# --- membership ----------------------------------------------------------------


def test_member_can_use_every_endpoint(api, card, member):
    created = api.add(card.id, "by member", as_user=member)
    assert created.status_code == 201
    item_id = created.json()["id"]

    assert api.list(card.id, as_user=member).status_code == 200
    assert api.card(card.id, as_user=member).status_code == 200
    assert api.patch(item_id, as_user=member, completed=True).status_code == 200
    assert api.delete(item_id, as_user=member).status_code == 204


def test_owner_without_member_row_still_has_access(api, card, session, owner):
    session.execute(BoardMember.__table__.delete())
    session.commit()

    assert api.add(card.id, "x").status_code == 201


def test_non_member_is_rejected_on_every_endpoint(api, card, outsider, session):
    (item_id,) = api.seed(card.id, "secret")

    assert api.add(card.id, "x", as_user=outsider).status_code == 404
    assert api.list(card.id, as_user=outsider).status_code == 404
    assert api.card(card.id, as_user=outsider).status_code == 404
    assert api.patch(item_id, as_user=outsider, completed=True).status_code == 404
    assert api.delete(item_id, as_user=outsider).status_code == 404
    # Nothing leaked and nothing changed.
    assert db_positions(session, card.id) == [("secret", 0)]
    assert session.get(ChecklistItem, item_id).completed is False


def test_member_of_another_board_is_rejected(api, card, outsider, session):
    other_board = make_board(session, outsider)
    other_card = make_card(session, other_board, title="Theirs")
    their_item = api.add(other_card.id, "theirs", as_user=outsider).json()["id"]

    assert api.patch(their_item, completed=True).status_code == 404
    assert api.add(card.id, "x", as_user=outsider).status_code == 404
