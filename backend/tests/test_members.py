import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Board, BoardMember, Card, User
from app.services.auth import create_access_token

MEMBER_KEYS = {"user_id", "email", "display_name", "role", "created_at"}
BOARD_KEYS = {"id", "name", "owner_id", "role", "created_at", "updated_at"}


def make_user(session: Session, email: str) -> User:
    user = User(email=email, password_hash="not-a-real-hash", display_name=email.split("@")[0].title())
    session.add(user)
    session.commit()
    return user


def headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def member_rows(session: Session, board_id: int) -> list[tuple[int, str]]:
    session.expire_all()
    rows = session.scalars(
        select(BoardMember).where(BoardMember.board_id == board_id).order_by(BoardMember.id)
    )
    return [(m.user_id, m.role) for m in rows]


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
def board_id(client: TestClient, session: Session, owner: User, member: User) -> int:
    board_id = client.post("/boards", json={"name": "Roadmap"}, headers=headers(owner)).json()["id"]
    session.add(BoardMember(board_id=board_id, user_id=member.id, role="member"))
    session.commit()
    return board_id


@pytest.fixture
def api(client: TestClient, owner: User):
    class Api:
        def invite(self, board_id: int, as_user: User = owner):
            return client.post(f"/boards/{board_id}/invite", headers=headers(as_user))

        def join(self, token: str, as_user: User = owner):
            return client.post(f"/invite/{token}/join", headers=headers(as_user))

        def members(self, board_id: int, as_user: User = owner):
            return client.get(f"/boards/{board_id}/members", headers=headers(as_user))

        def add(self, board_id: int, email: str, as_user: User = owner):
            return client.post(
                f"/boards/{board_id}/members", json={"email": email}, headers=headers(as_user)
            )

        def remove(self, board_id: int, user_id: int, as_user: User = owner):
            return client.delete(f"/boards/{board_id}/members/{user_id}", headers=headers(as_user))

        def token(self, board_id: int) -> str:
            return self.invite(board_id).json()["invite_token"]

    return Api()


# --- invite token ----------------------------------------------------------------


def test_owner_gets_a_permanent_invite_token(api, board_id, session):
    first = api.invite(board_id)

    assert first.status_code == 200
    body = first.json()
    assert body.keys() == {"board_id", "invite_token", "invite_path"}
    assert body["board_id"] == board_id
    assert len(body["invite_token"]) >= 32
    assert body["invite_path"] == f"/invite/{body['invite_token']}"
    assert api.invite(board_id).json() == body  # same token every time
    session.expire_all()
    assert session.get(Board, board_id).invite_token == body["invite_token"]


def test_tokens_differ_between_boards(api, board_id, client, owner):
    other = client.post("/boards", json={"name": "Other"}, headers=headers(owner)).json()["id"]
    assert api.token(board_id) != api.token(other)


def test_member_cannot_fetch_invite_token(api, board_id, member):
    response = api.invite(board_id, as_user=member)

    assert response.status_code == 403
    assert response.json() == {"detail": "Only the board owner can do this"}


def test_non_member_cannot_fetch_invite_token(api, board_id, outsider):
    assert api.invite(board_id, as_user=outsider).status_code == 404


def test_new_board_has_no_token_until_asked(client, owner, session):
    board_id = client.post("/boards", json={"name": "Fresh"}, headers=headers(owner)).json()["id"]
    assert session.get(Board, board_id).invite_token is None


# --- join ----------------------------------------------------------------------


def test_join_via_valid_token(api, board_id, outsider, session, client):
    token = api.token(board_id)

    response = api.join(token, as_user=outsider)

    assert response.status_code == 200
    body = response.json()
    assert body["joined"] is True
    assert body["board"].keys() == BOARD_KEYS
    assert (body["board"]["id"], body["board"]["role"]) == (board_id, "member")
    assert member_rows(session, board_id)[-1] == (outsider.id, "member")
    # The new member can now see the board.
    assert client.get(f"/boards/{board_id}", headers=headers(outsider)).status_code == 200


def test_join_twice_is_idempotent(api, board_id, outsider, session):
    token = api.token(board_id)
    api.join(token, as_user=outsider)

    response = api.join(token, as_user=outsider)

    assert response.status_code == 200
    assert response.json()["joined"] is False
    assert member_rows(session, board_id).count((outsider.id, "member")) == 1
    assert session.scalar(select(func.count()).select_from(BoardMember)) == 3


def test_owner_joining_own_board_is_a_noop(api, board_id, owner, session):
    response = api.join(api.token(board_id))

    assert response.status_code == 200
    assert response.json()["joined"] is False
    assert response.json()["board"]["role"] == "owner"
    assert member_rows(session, board_id).count((owner.id, "owner")) == 1
    assert len(member_rows(session, board_id)) == 2


@pytest.mark.parametrize("token", ["nope", "a" * 43])
def test_invalid_token_is_rejected(api, board_id, outsider, token, session):
    api.token(board_id)

    response = api.join(token, as_user=outsider)

    assert response.status_code == 404
    assert response.json() == {"detail": "Invalid invite link"}
    assert (outsider.id, "member") not in member_rows(session, board_id)


def test_join_requires_token(client, api, board_id):
    assert client.post(f"/invite/{api.token(board_id)}/join").status_code == 401


# --- list members ------------------------------------------------------------------


def test_list_members_owner_first(api, board_id, owner, member, outsider):
    api.join(api.token(board_id), as_user=outsider)

    response = api.members(board_id, as_user=member)

    assert response.status_code == 200
    body = response.json()
    assert all(m.keys() == MEMBER_KEYS for m in body)
    assert [(m["user_id"], m["role"], m["display_name"], m["email"]) for m in body] == [
        (owner.id, "owner", "Owner", "owner@example.com"),
        (member.id, "member", "Member", "member@example.com"),
        (outsider.id, "member", "Outsider", "outsider@example.com"),
    ]
    assert all(m["created_at"].endswith(("Z", "+00:00")) for m in body)


def test_non_member_cannot_list_members(api, board_id, outsider):
    assert api.members(board_id, as_user=outsider).status_code == 404


# --- invite by email ---------------------------------------------------------------


def test_owner_adds_existing_user_by_email(api, board_id, outsider, session):
    response = api.add(board_id, "  Outsider@Example.com ")

    assert response.status_code == 201
    body = response.json()
    assert body.keys() == MEMBER_KEYS
    assert (body["user_id"], body["role"]) == (outsider.id, "member")
    assert (outsider.id, "member") in member_rows(session, board_id)


def test_adding_an_existing_member_is_idempotent(api, board_id, member, session):
    response = api.add(board_id, "member@example.com")

    assert response.status_code == 200
    assert response.json()["user_id"] == member.id
    assert member_rows(session, board_id).count((member.id, "member")) == 1


def test_adding_the_owner_returns_the_owner_row(api, board_id, owner):
    response = api.add(board_id, "owner@example.com")
    assert (response.status_code, response.json()["role"]) == (200, "owner")


def test_adding_unknown_email_is_404(api, board_id):
    response = api.add(board_id, "nobody@example.com")

    assert response.status_code == 404
    assert response.json() == {"detail": "No user with this email"}


def test_add_requires_email_field(client, board_id, owner):
    assert client.post(f"/boards/{board_id}/members", json={}, headers=headers(owner)).status_code == 422


def test_member_cannot_invite_by_email(api, board_id, member, outsider, session):
    assert api.add(board_id, "outsider@example.com", as_user=member).status_code == 403
    assert (outsider.id, "member") not in member_rows(session, board_id)


# --- remove ------------------------------------------------------------------------


def test_owner_removes_member_and_unassigns_their_cards(api, board_id, owner, member, session, client):
    column_id = session.get(Board, board_id).columns[0].id
    card = client.post(
        f"/boards/{board_id}/cards",
        json={"title": "t", "column_id": column_id, "assignee_id": member.id},
        headers=headers(owner),
    ).json()
    other_board = client.post("/boards", json={"name": "Other"}, headers=headers(owner)).json()
    session.add(BoardMember(board_id=other_board["id"], user_id=member.id, role="member"))
    session.commit()
    other_card = client.post(
        f"/boards/{other_board['id']}/cards",
        json={"title": "t", "column_id": other_board["columns"][0]["id"], "assignee_id": member.id},
        headers=headers(owner),
    ).json()

    response = api.remove(board_id, member.id)

    assert response.status_code == 204
    assert response.content == b""
    assert member_rows(session, board_id) == [(owner.id, "owner")]
    assert session.get(Card, card["id"]).assignee_id is None
    assert session.get(Card, other_card["id"]).assignee_id == member.id  # other board untouched
    assert client.get(f"/boards/{board_id}", headers=headers(member)).status_code == 404
    assert session.get(User, member.id) is not None


def test_removed_member_can_rejoin_with_the_link(api, board_id, member, session):
    token = api.token(board_id)
    api.remove(board_id, member.id)

    assert api.join(token, as_user=member).json()["joined"] is True
    assert (member.id, "member") in member_rows(session, board_id)


def test_owner_cannot_be_removed(api, board_id, owner, session):
    response = api.remove(board_id, owner.id)

    assert response.status_code == 409
    assert response.json() == {"detail": "The owner cannot be removed"}
    assert (owner.id, "owner") in member_rows(session, board_id)


def test_non_owner_cannot_remove_members(api, board_id, member, outsider, session):
    api.join(api.token(board_id), as_user=outsider)

    assert api.remove(board_id, outsider.id, as_user=member).status_code == 403
    assert api.remove(board_id, member.id, as_user=member).status_code == 403  # not even themselves
    assert api.remove(board_id, member.id, as_user=outsider).status_code == 403
    assert len(member_rows(session, board_id)) == 3


def test_non_member_gets_404_on_remove(api, board_id, member, outsider):
    assert api.remove(board_id, member.id, as_user=outsider).status_code == 404


def test_removing_a_non_member_is_404(api, board_id, outsider):
    response = api.remove(board_id, outsider.id)

    assert response.status_code == 404
    assert response.json() == {"detail": "Member not found"}
