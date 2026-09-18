import importlib.util
import sys
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import utcnow
from app.models import Board, BoardMember, Card, ChecklistItem, Column, Comment, Label, User

SEED_PATH = Path(__file__).resolve().parents[1] / "scripts" / "seed.py"


@pytest.fixture(scope="module")
def seed_module():
    spec = importlib.util.spec_from_file_location("seed", SEED_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["seed"] = module
    spec.loader.exec_module(module)
    return module


def count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def all_counts(session: Session) -> dict[str, int]:
    return {m.__tablename__: count(session, m) for m in (User, Board, BoardMember, Column, Label, Card, ChecklistItem, Comment)}


def test_seed_creates_the_demo_board(session: Session, seed_module):
    created = seed_module.seed(session)

    assert created == {
        "users": 3, "boards": 1, "board_members": 3, "columns": 5, "labels": 5,
        "cards": 14, "checklist_items": 19, "comments": 7,
    }
    assert all_counts(session) == {
        "users": 3, "boards": 1, "board_members": 3, "columns": 5, "labels": 5,
        "cards": 14, "checklist_items": 19, "comments": 7,
    }
    board = session.scalar(select(Board).where(Board.name == "Insurance Policy Automation"))
    assert [c.name for c in sorted(board.columns, key=lambda c: c.position)] == [
        "Backlog", "To Do", "In Progress", "Review", "Done"
    ]
    assert board.owner.email == "ada@example.com"


def test_seed_is_idempotent(session: Session, seed_module):
    seed_module.seed(session)
    first = all_counts(session)

    created = seed_module.seed(session)

    assert all(value == 0 for value in created.values())
    assert all_counts(session) == first


def test_seed_content_covers_every_kind_of_data(session: Session, seed_module):
    seed_module.seed(session)
    cards = list(session.scalars(select(Card)))

    assert {c.priority for c in cards} == {"low", "medium", "high"}
    overdue = [c for c in cards if c.due_date is not None and c.due_date < utcnow()]
    assert len(overdue) >= 3
    assert any(c.due_date is not None and c.due_date > utcnow() for c in cards)
    assert any(c.due_date is None for c in cards)
    assert {c.assignee_id for c in cards if c.assignee_id} == {u.id for u in session.scalars(select(User))}
    assert sum(1 for c in cards if c.labels) >= 10
    assert sum(1 for c in cards if c.checklist_items) >= 6
    assert sum(1 for c in cards if c.comments) >= 5
    children = [c for c in cards if c.parent_card_id is not None]
    assert len(children) == 2
    assert all(child.parent.column_id == child.column_id for child in children)
    assert all(child.board_id == child.parent.board_id for child in children)


def test_seed_positions_are_contiguous_per_column(session: Session, seed_module):
    seed_module.seed(session)
    for column in session.scalars(select(Column)):
        positions = sorted(c.position for c in column.cards)
        assert positions == list(range(len(positions)))


def test_seed_labels_belong_to_the_board_and_attach_to_cards(session: Session, seed_module):
    seed_module.seed(session)
    board = session.scalar(select(Board))
    assert {l.name for l in board.labels} == {"bug", "feature", "compliance", "integration", "urgent"}
    urgent = session.scalar(select(Label).where(Label.name == "urgent"))
    assert [c.title for c in urgent.cards] == ["Regulator quarterly export"]


def test_seeded_users_can_log_in_and_see_the_board(client, session: Session, seed_module):
    seed_module.seed(session)

    login = client.post("/auth/login", json={"email": "Grace@example.com", "password": "insurance-demo"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    boards = client.get("/boards", headers={"Authorization": f"Bearer {token}"}).json()
    assert [(b["name"], b["role"]) for b in boards] == [("Insurance Policy Automation", "member")]
    board_id = boards[0]["id"]
    dashboard = client.get(f"/boards/{board_id}/dashboard", headers={"Authorization": f"Bearer {token}"}).json()
    assert dashboard["total"] == 14
    assert dashboard["overdue"] == 3  # past due and not in Done
    assert dashboard["done"] == 2


def test_seed_hashes_passwords_with_bcrypt(session: Session, seed_module):
    seed_module.seed(session)
    for user in session.scalars(select(User)):
        assert user.password_hash.startswith("$2b$")
        assert user.email == user.email.strip().lower()


def test_main_prints_summary_then_nothing_to_do(seed_module, capsys, monkeypatch):
    # Point the script's session factory at a fresh in-memory engine so main()
    # never touches a file database.
    from sqlalchemy.orm import sessionmaker
    from app.database import Base, make_engine
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(seed_module, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(seed_module, "create_all", lambda: None)

    seed_module.main()
    seed_module.main()

    out = capsys.readouterr().out
    assert "Seeded: 3 users, 1 boards" in out
    assert "insurance-demo" in out
    assert "Nothing to do" in out
    engine.dispose()
