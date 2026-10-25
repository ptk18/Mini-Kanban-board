"""Demo fault injection (issue #45): off by default, invisible without the
environment variable, and when switched on it makes card moves fail with 500
in a way the error-rate alert can see."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import fault
from app.main import app as fastapi_app
from app.models import Board, BoardMember, Card, Column, User
from app.routers import debug
from app.services.auth import create_access_token


@pytest.fixture(autouse=True)
def fault_off():
    fault.STATE.card_move_fails = False
    yield
    fault.STATE.card_move_fails = False


@pytest.mark.parametrize("value,expected", [("", False), ("0", False), ("false", False), ("1", True), ("yes", True)])
def test_enabled_by_env(monkeypatch, value, expected):
    monkeypatch.setenv("FAULT_INJECTION", value)
    assert fault.enabled_by_env() is expected


def test_debug_route_is_not_registered_without_the_variable():
    paths = {getattr(route, "path", None) for route in fastapi_app.routes}
    assert "/debug/fault" not in paths


def test_debug_route_toggles_the_fault():
    app = FastAPI()
    app.include_router(debug.router)
    client = TestClient(app)
    assert client.get("/debug/fault").json() == {"card_move_fails": False}
    assert client.post("/debug/fault", json={"card_move_fails": True}).json() == {"card_move_fails": True}
    assert fault.STATE.card_move_fails is True
    assert client.post("/debug/fault", json={"card_move_fails": False}).json() == {"card_move_fails": False}


@pytest.fixture
def moving(session: Session, client: TestClient):
    user = User(email="u@example.com", password_hash="h", display_name="U")
    session.add(user)
    session.flush()
    board = Board(name="B", owner_id=user.id)
    session.add(board)
    session.flush()
    session.add(BoardMember(board_id=board.id, user_id=user.id, role="owner"))
    a = Column(board_id=board.id, name="A", position=0)
    b = Column(board_id=board.id, name="B", position=1)
    session.add_all([a, b])
    session.flush()
    card = Card(board_id=board.id, column_id=a.id, title="c", position=0)
    session.add(card)
    session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}

    def move(column_id):
        return client.patch(f"/cards/{card.id}", json={"column_id": column_id}, headers=headers)

    return move, a, b, card, session


def test_fault_makes_moves_fail_with_500_and_leaves_the_card_in_place(moving, log_lines):
    move, a, b, card, session = moving
    fault.STATE.card_move_fails = True
    client_app = fastapi_app  # TestClient raises server exceptions by default; use a non-raising one
    raw = TestClient(client_app, raise_server_exceptions=False)
    from app.database import get_db

    headers = {"Authorization": f"Bearer {create_access_token(card.board.owner_id)}"}
    response = raw.patch(f"/cards/{card.id}", json={"column_id": b.id}, headers=headers)
    assert response.status_code == 500

    session.expire_all()
    assert session.get(Card, card.id).column_id == a.id

    entries = [line for line in log_lines() if line.get("event") == "http.request"]
    assert entries[-1]["level"] == "error"
    assert entries[-1]["http.response.status_code"] == 500
    assert entries[-1]["error.type"] == "InjectedFault"
    assert "card moves are set to fail" in entries[-1]["error.message"]

    # Reorders inside the column and plain edits are unaffected by the fault.
    assert move(a.id).status_code == 200

    fault.STATE.card_move_fails = False
    assert move(b.id).status_code == 200
