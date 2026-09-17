import time
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (
    Activity,
    Board,
    BoardMember,
    Card,
    CardLabel,
    ChecklistItem,
    Column,
    Comment,
    Label,
    User,
)

TABLE_NAMES = {
    "activities",
    "board_members",
    "boards",
    "card_labels",
    "cards",
    "checklist_items",
    "columns",
    "comments",
    "labels",
    "users",
}

ALL_MODELS = [User, Board, BoardMember, Column, Card, Label, CardLabel, ChecklistItem, Comment, Activity]


def count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def make_user(session: Session, email: str = "alice@example.com") -> User:
    user = User(email=email, password_hash="not-a-real-hash", display_name="Alice")
    session.add(user)
    session.commit()
    return user


def make_board(session: Session, owner: User) -> Board:
    board = Board(name="Roadmap", owner_id=owner.id)
    session.add(board)
    session.commit()
    return board


def make_column(session: Session, board: Board, name: str = "Todo", position: int = 0) -> Column:
    column = Column(board_id=board.id, name=name, position=position)
    session.add(column)
    session.commit()
    return column


def make_card(session: Session, board: Board, column: Column, title: str = "Write tests", **kw) -> Card:
    card = Card(board_id=board.id, column_id=column.id, title=title, position=kw.pop("position", 0), **kw)
    session.add(card)
    session.commit()
    return card


@pytest.fixture
def graph(session: Session) -> dict:
    """One row of every model, wired together the way the app will use them."""
    user = make_user(session)
    board = make_board(session, user)
    member = BoardMember(board_id=board.id, user_id=user.id, role="owner")
    column = make_column(session, board)
    card = make_card(session, board, column, assignee_id=user.id)
    label = Label(board_id=board.id, name="bug")
    session.add_all([member, label])
    session.commit()
    card_label = CardLabel(card_id=card.id, label_id=label.id)
    item = ChecklistItem(card_id=card.id, content="step one", position=0)
    comment = Comment(card_id=card.id, user_id=user.id, content="looks good")
    activity = Activity(board_id=board.id, user_id=user.id, card_id=card.id, action="created card")
    session.add_all([card_label, item, comment, activity])
    session.commit()
    return {
        "user": user,
        "board": board,
        "member": member,
        "column": column,
        "card": card,
        "label": label,
        "card_label": card_label,
        "item": item,
        "comment": comment,
        "activity": activity,
    }


def test_metadata_has_exactly_the_ten_tables():
    assert set(Base.metadata.tables) == TABLE_NAMES


def test_one_row_per_model_inserts_and_reads_back(session: Session, graph: dict):
    for model in ALL_MODELS:
        assert count(session, model) == 1, model.__name__

    assert session.get(User, graph["user"].id) is graph["user"]
    assert session.get(Board, graph["board"].id) is graph["board"]
    assert session.get(BoardMember, graph["member"].id) is graph["member"]
    assert session.get(Column, graph["column"].id) is graph["column"]
    assert session.get(Card, graph["card"].id) is graph["card"]
    assert session.get(Label, graph["label"].id) is graph["label"]
    assert session.get(CardLabel, (graph["card"].id, graph["label"].id)) is graph["card_label"]
    assert session.get(ChecklistItem, graph["item"].id) is graph["item"]
    assert session.get(Comment, graph["comment"].id) is graph["comment"]
    assert session.get(Activity, graph["activity"].id) is graph["activity"]


def test_column_defaults(session: Session, graph: dict):
    card = graph["card"]
    assert card.description == ""
    assert card.priority == "medium"
    assert card.due_date is None
    assert card.parent_card_id is None
    assert graph["item"].completed is False
    assert graph["activity"].card_id == card.id


def test_card_with_missing_column_raises_integrity_error(session: Session):
    user = make_user(session)
    board = make_board(session, user)
    session.add(Card(board_id=board.id, column_id=999, title="orphan", position=0))
    with pytest.raises(IntegrityError):
        session.commit()


def test_duplicate_user_email_raises(session: Session, graph: dict):
    session.add(User(email=graph["user"].email, password_hash="x", display_name="Dup"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_duplicate_board_membership_raises(session: Session, graph: dict):
    session.add(BoardMember(board_id=graph["board"].id, user_id=graph["user"].id, role="member"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_duplicate_label_name_on_board_raises(session: Session, graph: dict):
    session.add(Label(board_id=graph["board"].id, name=graph["label"].name))
    with pytest.raises(IntegrityError):
        session.commit()


def test_same_label_name_on_another_board_is_allowed(session: Session, graph: dict):
    other = make_board(session, graph["user"])
    session.add(Label(board_id=other.id, name=graph["label"].name))
    session.commit()
    assert count(session, Label) == 2


def test_duplicate_card_label_pair_raises(session: Session, graph: dict):
    card_id, label_id = graph["card"].id, graph["label"].id
    # A second request would use a fresh session; drop the identity map so the
    # database constraint, not SQLAlchemy's identity check, is what rejects it.
    session.expunge_all()
    session.add(CardLabel(card_id=card_id, label_id=label_id))
    with pytest.raises(IntegrityError):
        session.commit()


def test_invalid_role_raises(session: Session, graph: dict):
    other = make_user(session, "bob@example.com")
    session.add(BoardMember(board_id=graph["board"].id, user_id=other.id, role="admin"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_invalid_priority_raises(session: Session, graph: dict):
    session.add(
        Card(board_id=graph["board"].id, column_id=graph["column"].id, title="x", position=1, priority="urgent")
    )
    with pytest.raises(IntegrityError):
        session.commit()


@pytest.mark.parametrize("priority", ["low", "medium", "high"])
def test_valid_priorities_are_accepted(session: Session, graph: dict, priority: str):
    make_card(session, graph["board"], graph["column"], title=priority, position=1, priority=priority)


def test_deleting_board_cascades_to_everything_but_the_user(session: Session, graph: dict):
    session.delete(graph["board"])
    session.commit()

    for model in (Board, BoardMember, Column, Card, Label, CardLabel, ChecklistItem, Comment, Activity):
        assert count(session, model) == 0, model.__name__
    assert count(session, User) == 1


def test_deleting_board_with_loaded_collections_also_cascades(session: Session, graph: dict):
    board = session.get(Board, graph["board"].id)
    # Touch every relationship so the ORM, not only SQLite, drives the delete.
    assert len(board.columns) == 1
    assert len(board.cards) == 1
    assert len(board.members) == 1
    assert len(board.labels) == 1
    assert len(board.activities) == 1
    assert len(board.cards[0].labels) == 1

    session.delete(board)
    session.commit()

    for model in (Board, BoardMember, Column, Card, Label, CardLabel, ChecklistItem, Comment, Activity):
        assert count(session, model) == 0, model.__name__
    assert count(session, User) == 1


def test_deleting_card_removes_children_rows_and_detaches_child_card_and_activity(
    session: Session, graph: dict
):
    parent = graph["card"]
    child = make_card(session, graph["board"], graph["column"], title="subtask", position=1, parent_card_id=parent.id)
    child_id = child.id
    activity_id = graph["activity"].id

    session.delete(parent)
    session.commit()

    assert count(session, Card) == 1
    assert count(session, ChecklistItem) == 0
    assert count(session, Comment) == 0
    assert count(session, CardLabel) == 0
    assert count(session, Label) == 1
    assert session.get(Card, child_id).parent_card_id is None
    remaining = session.get(Activity, activity_id)
    assert remaining is not None
    assert remaining.card_id is None


def test_deleting_column_with_cards_raises(session: Session, graph: dict):
    session.delete(graph["column"])
    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_empty_column_works(session: Session, graph: dict):
    empty = make_column(session, graph["board"], name="Done", position=1)
    session.delete(empty)
    session.commit()
    assert count(session, Column) == 1


def test_deleting_board_owner_raises(session: Session, graph: dict):
    session.delete(graph["user"])
    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_assignee_sets_card_assignee_null(session: Session, graph: dict):
    assignee = make_user(session, "carol@example.com")
    card = make_card(session, graph["board"], graph["column"], title="assigned", position=1, assignee_id=assignee.id)
    card_id = card.id

    session.delete(assignee)
    session.commit()

    assert session.get(Card, card_id).assignee_id is None


def test_created_at_is_populated_naive_utc(session: Session, graph: dict):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for name in ("user", "board", "member", "column", "card", "comment", "activity"):
        created = graph[name].created_at
        assert created is not None, name
        assert created.tzinfo is None, name
        assert abs((now - created).total_seconds()) < 5, name


@pytest.mark.parametrize(
    ("name", "field", "value"),
    [("card", "title", "renamed"), ("board", "name", "renamed"), ("comment", "content", "edited")],
)
def test_updated_at_advances_on_change(session: Session, graph: dict, name: str, field: str, value: str):
    obj = graph[name]
    created_before = obj.created_at
    updated_before = obj.updated_at
    assert updated_before >= created_before

    time.sleep(0.002)
    setattr(obj, field, value)
    session.commit()

    assert obj.updated_at > updated_before
    assert obj.updated_at >= obj.created_at
    assert obj.created_at == created_before
    assert obj.updated_at.tzinfo is None


def test_sqlalchemy_column_is_not_used_in_models():
    import pathlib
    import re

    models_dir = pathlib.Path(__file__).resolve().parent.parent / "app" / "models"
    for path in models_dir.glob("*.py"):
        source = path.read_text()
        assert not re.search(r"^from sqlalchemy import .*\bColumn\b", source, re.M), path.name
        assert "sqlalchemy.Column" not in source, path.name
        assert "declarative_base" not in source, path.name
