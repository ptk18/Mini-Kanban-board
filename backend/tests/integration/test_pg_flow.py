"""The main user journey through the HTTP API against Postgres: sign up, log
in, create a board, add and move a card, read the dashboard — plus the access
rules and the pieces of behaviour that depend on the database engine
(cascades, uniqueness, timestamps)."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import utcnow
from app.models import Card, Comment, User


def signup(client: TestClient, email: str, name: str = "Someone") -> dict[str, str]:
    r = client.post(
        "/auth/signup",
        json={"email": email, "password": "correct horse battery", "display_name": name},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_signup_login_board_card_move_dashboard(pg_client: TestClient, pg_session: Session):
    headers = signup(pg_client, "ada@example.com", "Ada")

    login = pg_client.post(
        "/auth/login", json={"email": "ADA@example.com ", "password": "correct horse battery"}
    )
    assert login.status_code == 200
    assert login.json()["user"]["email"] == "ada@example.com"

    board = pg_client.post("/boards", json={"name": "Roadmap"}, headers=headers)
    assert board.status_code == 201
    board_id = board.json()["id"]
    columns = board.json()["columns"]
    assert [c["name"] for c in columns] == ["To Do", "In Progress", "Done"]
    todo, _, done = columns

    created = pg_client.post(
        f"/boards/{board_id}/cards",
        json={
            "title": "Ship it",
            "column_id": todo["id"],
            "priority": "high",
            "due_date": (utcnow() - timedelta(days=1)).isoformat() + "Z",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    card = created.json()
    assert card["created_at"].endswith("Z")

    before = pg_client.get(f"/boards/{board_id}/dashboard", headers=headers).json()
    assert (before["total"], before["overdue"], before["done"]) == (1, 1, 0)

    moved = pg_client.patch(
        f"/cards/{card['id']}", json={"column_id": done["id"], "position": 0}, headers=headers
    )
    assert moved.status_code == 200
    assert moved.json()["column_id"] == done["id"]
    assert moved.json()["updated_at"] >= card["updated_at"]

    after = pg_client.get(f"/boards/{board_id}/dashboard", headers=headers).json()
    assert (after["total"], after["overdue"], after["done"]) == (1, 0, 1)
    assert after["progress_percent"] == 100.0

    pg_session.expire_all()
    row = pg_session.get(Card, card["id"])
    assert row.column_id == done["id"]
    assert row.due_date.tzinfo is None  # naive UTC round-trips on Postgres


def test_non_member_gets_404_and_member_cannot_delete(pg_client: TestClient):
    owner = signup(pg_client, "owner@example.com")
    member = signup(pg_client, "member@example.com")
    outsider = signup(pg_client, "outsider@example.com")

    board_id = pg_client.post("/boards", json={"name": "Private"}, headers=owner).json()["id"]
    assert pg_client.get(f"/boards/{board_id}", headers=outsider).status_code == 404

    added = pg_client.post(
        f"/boards/{board_id}/members", json={"email": "member@example.com"}, headers=owner
    )
    assert added.status_code == 201
    assert pg_client.get(f"/boards/{board_id}", headers=member).status_code == 200
    assert pg_client.delete(f"/boards/{board_id}", headers=member).status_code == 403
    assert pg_client.delete(f"/boards/{board_id}", headers=owner).status_code == 204
    assert pg_client.get(f"/boards/{board_id}", headers=owner).status_code == 404


def test_deleting_a_board_cascades_in_the_database(pg_client: TestClient, pg_session: Session):
    headers = signup(pg_client, "ada@example.com")
    board = pg_client.post("/boards", json={"name": "Temp"}, headers=headers).json()
    card = pg_client.post(
        f"/boards/{board['id']}/cards",
        json={"title": "Doomed", "column_id": board["columns"][0]["id"]},
        headers=headers,
    ).json()
    pg_client.post(f"/cards/{card['id']}/comments", json={"content": "bye"}, headers=headers)
    pg_client.post(f"/cards/{card['id']}/checklist", json={"content": "step"}, headers=headers)

    assert pg_client.delete(f"/boards/{board['id']}", headers=headers).status_code == 204

    pg_session.expire_all()
    assert pg_session.scalars(select(Card)).all() == []
    assert pg_session.scalars(select(Comment)).all() == []
    assert pg_session.scalars(select(User)).one().email == "ada@example.com"


def test_duplicate_email_is_rejected_by_the_unique_index(pg_client: TestClient):
    signup(pg_client, "ada@example.com")
    r = pg_client.post(
        "/auth/signup",
        json={"email": "Ada@Example.com", "password": "another password", "display_name": "Ada"},
    )
    assert r.status_code == 409


@pytest.mark.parametrize("path", ["/boards", "/boards/1", "/cards/1", "/boards/1/dashboard"])
def test_missing_token_is_401_on_postgres_too(pg_client: TestClient, path: str):
    r = pg_client.get(path)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
