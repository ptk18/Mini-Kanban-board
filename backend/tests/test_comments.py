from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Board, BoardMember, Card, Column, Comment, User
from app.services.auth import create_access_token

COMMENT_KEYS = {"id", "card_id", "author", "content", "created_at", "updated_at"}


def make_user(session: Session, email: str, display_name: str) -> User:
    user = User(email=email, password_hash="not-a-real-hash", display_name=display_name)
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


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


@pytest.fixture
def owner(session: Session) -> User:
    return make_user(session, "owner@example.com", "Owner")


@pytest.fixture
def member(session: Session) -> User:
    return make_user(session, "member@example.com", "Member")


@pytest.fixture
def outsider(session: Session) -> User:
    return make_user(session, "outsider@example.com", "Outsider")


@pytest.fixture
def card(session: Session, owner: User, member: User) -> Card:
    return make_card(session, make_board(session, owner, member))


@pytest.fixture
def api(client: TestClient, owner: User):
    class Api:
        def post(self, card_id: int, content: str, as_user: User = owner):
            return client.post(
                f"/cards/{card_id}/comments", json={"content": content}, headers=headers(as_user)
            )

        def list(self, card_id: int, as_user: User = owner):
            return client.get(f"/cards/{card_id}/comments", headers=headers(as_user))

        def patch(self, comment_id: int, content: str, as_user: User = owner):
            return client.patch(
                f"/comments/{comment_id}", json={"content": content}, headers=headers(as_user)
            )

        def delete(self, comment_id: int, as_user: User = owner):
            return client.delete(f"/comments/{comment_id}", headers=headers(as_user))

    return Api()


# --- post ----------------------------------------------------------------------


def test_post_comment_records_author_and_timestamps(api, card, owner, session):
    response = api.post(card.id, "  First!  ")

    assert response.status_code == 201
    body = response.json()
    assert body.keys() == COMMENT_KEYS
    assert body["card_id"] == card.id
    assert body["content"] == "First!"
    assert body["author"] == {"id": owner.id, "display_name": "Owner"}
    assert body["created_at"].endswith(("Z", "+00:00"))
    assert body["updated_at"].endswith(("Z", "+00:00"))
    stored = session.get(Comment, body["id"])
    assert stored.user_id == owner.id
    assert stored.content == "First!"


def test_author_view_has_no_email(api, card):
    assert "email" not in api.post(card.id, "x").json()["author"]


@pytest.mark.parametrize("content", ["", "   ", "x" * 5001])
def test_post_rejects_bad_content(api, card, content):
    assert api.post(card.id, content).status_code == 422


def test_post_requires_token(client, card):
    assert client.post(f"/cards/{card.id}/comments", json={"content": "x"}).status_code == 401


def test_post_to_unknown_card_is_404(api):
    assert api.post(999, "x").status_code == 404


# --- list ----------------------------------------------------------------------


def test_list_is_chronological_with_each_authors_name(api, card, owner, member, session):
    api.post(card.id, "one", as_user=member)
    api.post(card.id, "two", as_user=owner)
    api.post(card.id, "three", as_user=member)

    response = api.list(card.id)

    assert response.status_code == 200
    body = response.json()
    assert [c["content"] for c in body] == ["one", "two", "three"]
    assert [c["author"]["display_name"] for c in body] == ["Member", "Owner", "Member"]
    stamps = [parse(c["created_at"]) for c in body]
    assert stamps == sorted(stamps)


def test_list_orders_by_created_at_not_id(api, card, owner, session):
    later = Comment(card_id=card.id, user_id=owner.id, content="later",
                    created_at=datetime(2026, 1, 2), updated_at=datetime(2026, 1, 2))
    earlier = Comment(card_id=card.id, user_id=owner.id, content="earlier",
                      created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1))
    session.add_all([later, earlier])
    session.commit()

    assert [c["content"] for c in api.list(card.id).json()] == ["earlier", "later"]


def test_list_only_returns_comments_of_that_card(api, card, session):
    other = make_card(session, session.get(Board, card.board_id), title="Other")
    api.post(card.id, "mine")
    api.post(other.id, "theirs")

    assert [c["content"] for c in api.list(card.id).json()] == ["mine"]


def test_list_empty(api, card):
    assert api.list(card.id).json() == []


# --- edit ----------------------------------------------------------------------


def test_author_can_edit_and_updated_at_moves(api, card):
    created = api.post(card.id, "typo").json()

    response = api.patch(created["id"], " fixed ")

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "fixed"
    assert body["author"] == created["author"]
    assert body["created_at"] == created["created_at"]
    assert parse(body["updated_at"]) > parse(created["updated_at"])


@pytest.mark.parametrize("content", ["", "   ", "x" * 5001])
def test_edit_rejects_bad_content(api, card, content):
    comment_id = api.post(card.id, "ok").json()["id"]
    assert api.patch(comment_id, content).status_code == 422


def test_other_member_cannot_edit(api, card, member, session):
    comment_id = api.post(card.id, "owner's").json()["id"]

    response = api.patch(comment_id, "hijacked", as_user=member)

    assert response.status_code == 403
    assert response.json() == {"detail": "Only the author can change this comment"}
    session.expire_all()
    assert session.get(Comment, comment_id).content == "owner's"


def test_edit_unknown_comment_is_404(api):
    assert api.patch(999, "x").status_code == 404


# --- delete --------------------------------------------------------------------


def test_author_can_delete(api, card, session):
    comment_id = api.post(card.id, "bye").json()["id"]

    response = api.delete(comment_id)

    assert response.status_code == 204
    assert response.content == b""
    assert session.get(Comment, comment_id) is None
    assert api.list(card.id).json() == []


def test_other_member_cannot_delete(api, card, member, session):
    comment_id = api.post(card.id, "owner's").json()["id"]

    assert api.delete(comment_id, as_user=member).status_code == 403
    assert session.get(Comment, comment_id) is not None


def test_member_can_delete_their_own_comment(api, card, member):
    comment_id = api.post(card.id, "mine", as_user=member).json()["id"]
    assert api.delete(comment_id, as_user=member).status_code == 204


def test_delete_unknown_comment_is_404(api):
    assert api.delete(999).status_code == 404


# --- membership ------------------------------------------------------------------


def test_member_can_post_and_read(api, card, member):
    assert api.post(card.id, "hi", as_user=member).status_code == 201
    assert api.list(card.id, as_user=member).status_code == 200


def test_non_member_is_rejected_on_every_endpoint(api, card, outsider, session):
    comment_id = api.post(card.id, "secret").json()["id"]

    assert api.post(card.id, "x", as_user=outsider).status_code == 404
    assert api.list(card.id, as_user=outsider).status_code == 404
    # 404, not 403: a non-member must not learn that the comment exists.
    assert api.patch(comment_id, "x", as_user=outsider).status_code == 404
    assert api.delete(comment_id, as_user=outsider).status_code == 404
    session.expire_all()
    assert session.get(Comment, comment_id).content == "secret"
