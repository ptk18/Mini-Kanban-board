from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Board, BoardMember, Card, CardLabel, ChecklistItem, Comment, Label, User
from app.services.auth import create_access_token

CARD_KEYS = {
    "id", "board_id", "column_id", "parent_card_id", "title", "description", "priority",
    "due_date", "assignee_id", "position", "created_at", "updated_at", "labels",
    "checklist_items",
}
LABEL_KEYS = {"id", "board_id", "name"}


def make_user(session: Session, email: str) -> User:
    user = User(email=email, password_hash="not-a-real-hash", display_name=email.split("@")[0])
    session.add(user)
    session.commit()
    return user


def headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def db_cards(session: Session, column_id: int) -> list[tuple[str, int]]:
    session.expire_all()
    rows = session.scalars(
        select(Card).where(Card.column_id == column_id).order_by(Card.position)
    )
    return [(c.title, c.position) for c in rows]


@pytest.fixture
def owner(session: Session) -> User:
    return make_user(session, "owner@example.com")


@pytest.fixture
def member(session: Session) -> User:
    return make_user(session, "member@example.com")


@pytest.fixture
def outsider(session: Session) -> User:
    return make_user(session, "outsider@example.com")


class Board3:
    """A board with its three default columns and one member."""

    def __init__(self, client: TestClient, session: Session, owner: User, member: User | None):
        self.id = client.post("/boards", json={"name": "Roadmap"}, headers=headers(owner)).json()["id"]
        if member is not None:
            session.add(BoardMember(board_id=self.id, user_id=member.id, role="member"))
            session.commit()
        self.todo, self.doing, self.done = [
            c.id for c in sorted(session.get(Board, self.id).columns, key=lambda c: c.position)
        ]


@pytest.fixture
def board(client, session, owner, member) -> Board3:
    return Board3(client, session, owner, member)


@pytest.fixture
def other_board(client, session, outsider) -> Board3:
    return Board3(client, session, outsider, None)


@pytest.fixture
def api(client: TestClient, owner: User):
    class Api:
        def create(self, board_id: int, as_user: User = owner, **body):
            return client.post(f"/boards/{board_id}/cards", json=body, headers=headers(as_user))

        def list(self, board_id: int, as_user: User = owner):
            return client.get(f"/boards/{board_id}/cards", headers=headers(as_user))

        def get(self, card_id: int, as_user: User = owner):
            return client.get(f"/cards/{card_id}", headers=headers(as_user))

        def patch(self, card_id: int, as_user: User = owner, **body):
            return client.patch(f"/cards/{card_id}", json=body, headers=headers(as_user))

        def delete(self, card_id: int, as_user: User = owner):
            return client.delete(f"/cards/{card_id}", headers=headers(as_user))

        def label(self, board_id: int, name: str, as_user: User = owner):
            return client.post(f"/boards/{board_id}/labels", json={"name": name}, headers=headers(as_user))

        def labels(self, board_id: int, as_user: User = owner):
            return client.get(f"/boards/{board_id}/labels", headers=headers(as_user))

        def rename_label(self, label_id: int, name: str, as_user: User = owner):
            return client.patch(f"/labels/{label_id}", json={"name": name}, headers=headers(as_user))

        def delete_label(self, label_id: int, as_user: User = owner):
            return client.delete(f"/labels/{label_id}", headers=headers(as_user))

        def seed(self, board_id: int, column_id: int, *titles: str) -> list[int]:
            return [self.create(board_id, title=t, column_id=column_id).json()["id"] for t in titles]

    return Api()


# --- create --------------------------------------------------------------------


def test_create_with_defaults(api, board, owner):
    response = api.create(board.id, title="  Ship it  ", column_id=board.todo)

    assert response.status_code == 201
    body = response.json()
    assert body.keys() == CARD_KEYS
    assert body["board_id"] == board.id
    assert body["column_id"] == board.todo
    assert body["title"] == "Ship it"
    assert body["description"] == ""
    assert body["priority"] == "medium"
    assert body["due_date"] is None
    assert body["assignee_id"] is None
    assert body["parent_card_id"] is None
    assert body["position"] == 0
    assert body["labels"] == []
    assert body["checklist_items"] == []
    assert body["created_at"].endswith(("Z", "+00:00"))


def test_create_with_every_field(api, board, owner, member, session):
    parent_id = api.create(board.id, title="Parent", column_id=board.todo).json()["id"]
    bug = api.label(board.id, "bug").json()["id"]
    ui = api.label(board.id, "ui").json()["id"]

    response = api.create(
        board.id,
        title="Child",
        description="details",
        column_id=board.doing,
        priority="high",
        due_date="2026-01-02T03:04:05+02:00",
        assignee_id=member.id,
        parent_card_id=parent_id,
        label_ids=[ui, bug],
    )

    assert response.status_code == 201
    body = response.json()
    assert body["description"] == "details"
    assert body["priority"] == "high"
    assert body["due_date"] == "2026-01-02T01:04:05Z"  # stored as UTC
    assert body["assignee_id"] == member.id
    assert body["parent_card_id"] == parent_id
    assert [l["name"] for l in body["labels"]] == ["bug", "ui"]  # by label id
    assert all(l.keys() == LABEL_KEYS for l in body["labels"])
    assert session.get(Card, body["id"]).due_date == datetime(2026, 1, 2, 1, 4, 5)


def test_create_appends_and_can_insert_at_position(api, board, session):
    api.seed(board.id, board.todo, "a", "b")

    inserted = api.create(board.id, title="c", column_id=board.todo, position=1)

    assert inserted.json()["position"] == 1
    assert db_cards(session, board.todo) == [("a", 0), ("c", 1), ("b", 2)]


def test_create_at_end_position_is_allowed(api, board, session):
    api.seed(board.id, board.todo, "a")
    assert api.create(board.id, title="b", column_id=board.todo, position=1).status_code == 201
    assert api.create(board.id, title="c", column_id=board.todo, position=5).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"title": ""},
        {"title": "x" * 201},
        {"description": "x" * 5001},
        {"priority": "urgent"},
        {"due_date": "not a date"},
        {"position": -1},
        {"label_ids": "bug"},
    ],
)
def test_create_rejects_invalid_values(api, board, body):
    payload = {"title": "ok", "column_id": board.todo, **body}
    assert api.create(board.id, **payload).status_code == 422


def test_create_requires_title_and_column(api, board):
    assert api.create(board.id, title="x").status_code == 422
    assert api.create(board.id, column_id=board.todo).status_code == 422


def test_create_rejects_column_of_another_board(api, board, other_board):
    response = api.create(board.id, title="x", column_id=other_board.todo)

    assert response.status_code == 422
    assert response.json()["detail"] == "column_id must be a column of this board"


def test_create_rejects_non_member_assignee(api, board, outsider):
    response = api.create(board.id, title="x", column_id=board.todo, assignee_id=outsider.id)

    assert response.status_code == 422
    assert response.json()["detail"] == "assignee_id must be a member of this board"


def test_card_cannot_reference_parent_on_another_board(api, board, other_board, outsider):
    theirs = api.create(other_board.id, title="Theirs", column_id=other_board.todo, as_user=outsider).json()["id"]

    response = api.create(board.id, title="x", column_id=board.todo, parent_card_id=theirs)

    assert response.status_code == 422
    assert response.json()["detail"] == "parent_card_id must be a card on this board"
    assert api.create(board.id, title="x", column_id=board.todo, parent_card_id=999).status_code == 422


def test_create_rejects_labels_of_another_board(api, board, other_board, outsider):
    theirs = api.label(other_board.id, "theirs", as_user=outsider).json()["id"]

    response = api.create(board.id, title="x", column_id=board.todo, label_ids=[theirs])

    assert response.status_code == 422
    assert response.json()["detail"] == "label_ids must all be labels of this board"


def test_create_on_unknown_board_is_404(api, board):
    assert api.create(999, title="x", column_id=board.todo).status_code == 404


# --- list / get ----------------------------------------------------------------


def test_list_orders_by_column_then_position(api, board, session):
    api.seed(board.id, board.done, "d1")
    a, b = api.seed(board.id, board.todo, "a", "b")
    api.patch(b, position=0)

    response = api.list(board.id)

    assert response.status_code == 200
    assert [c["title"] for c in response.json()] == ["b", "a", "d1"]
    assert all(c.keys() == CARD_KEYS for c in response.json())


def test_list_is_scoped_to_the_board(api, board, other_board, outsider):
    api.seed(board.id, board.todo, "mine")
    api.create(other_board.id, title="theirs", column_id=other_board.todo, as_user=outsider)

    assert [c["title"] for c in api.list(board.id).json()] == ["mine"]
    assert api.list(board.id, as_user=outsider).status_code == 404


def test_get_includes_labels_and_checklist(api, board, client, owner):
    bug = api.label(board.id, "bug").json()["id"]
    card_id = api.create(board.id, title="x", column_id=board.todo, label_ids=[bug]).json()["id"]
    client.post(f"/cards/{card_id}/checklist", json={"content": "step"}, headers=headers(owner))

    body = api.get(card_id).json()

    assert [l["name"] for l in body["labels"]] == ["bug"]
    assert [i["content"] for i in body["checklist_items"]] == ["step"]


# --- update --------------------------------------------------------------------


def test_update_fields(api, board, member, session):
    card_id = api.seed(board.id, board.todo, "old")[0]
    created = api.get(card_id).json()

    response = api.patch(
        card_id,
        title=" new ",
        description="desc",
        priority="low",
        due_date="2026-05-06T07:08:09Z",
        assignee_id=member.id,
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["title"], body["description"], body["priority"]) == ("new", "desc", "low")
    assert body["due_date"] == "2026-05-06T07:08:09Z"
    assert body["assignee_id"] == member.id
    assert body["position"] == 0
    assert body["created_at"] == created["created_at"]


def test_update_can_clear_nullable_fields(api, board, member):
    parent = api.seed(board.id, board.todo, "p")[0]
    card_id = api.create(
        board.id, title="c", column_id=board.todo, assignee_id=member.id,
        parent_card_id=parent, due_date="2026-01-01T00:00:00Z",
    ).json()["id"]

    body = api.patch(card_id, assignee_id=None, parent_card_id=None, due_date=None).json()

    assert (body["assignee_id"], body["parent_card_id"], body["due_date"]) == (None, None, None)


@pytest.mark.parametrize(
    "body",
    [{}, {"title": None}, {"title": ""}, {"priority": None}, {"priority": "urgent"},
     {"column_id": None}, {"position": None}, {"label_ids": None}, {"description": None}],
)
def test_update_rejects_invalid_bodies(api, board, body):
    card_id = api.seed(board.id, board.todo, "x")[0]
    assert api.patch(card_id, **body).status_code == 422


def test_update_rejects_off_board_references(api, board, other_board, outsider, member):
    card_id = api.seed(board.id, board.todo, "x")[0]
    theirs = api.create(other_board.id, title="t", column_id=other_board.todo, as_user=outsider).json()["id"]
    their_label = api.label(other_board.id, "l", as_user=outsider).json()["id"]

    assert api.patch(card_id, column_id=other_board.todo).status_code == 422
    assert api.patch(card_id, parent_card_id=theirs).status_code == 422
    assert api.patch(card_id, assignee_id=outsider.id).status_code == 422
    assert api.patch(card_id, label_ids=[their_label]).status_code == 422
    assert api.get(card_id).json()["column_id"] == board.todo


def test_parent_cannot_be_self_or_descendant(api, board):
    grand, parent, child = api.seed(board.id, board.todo, "grand", "parent", "child")
    api.patch(parent, parent_card_id=grand)
    api.patch(child, parent_card_id=parent)

    assert api.patch(child, parent_card_id=child).status_code == 422
    response = api.patch(grand, parent_card_id=child)
    assert response.status_code == 422
    assert response.json()["detail"] == "parent_card_id cannot be the card itself or a descendant"
    assert api.get(grand).json()["parent_card_id"] is None


def test_update_unknown_card_is_404(api):
    assert api.patch(999, title="x").status_code == 404


# --- move / reorder ------------------------------------------------------------


def test_move_to_another_column_appends_and_renumbers_source(api, board, session):
    a, b, c = api.seed(board.id, board.todo, "a", "b", "c")
    api.seed(board.id, board.doing, "x")

    response = api.patch(b, column_id=board.doing)

    assert response.status_code == 200
    assert (response.json()["column_id"], response.json()["position"]) == (board.doing, 1)
    assert db_cards(session, board.todo) == [("a", 0), ("c", 1)]
    assert db_cards(session, board.doing) == [("x", 0), ("b", 1)]


def test_move_to_another_column_at_position(api, board, session):
    a, b = api.seed(board.id, board.todo, "a", "b")
    api.seed(board.id, board.doing, "x", "y")

    api.patch(a, column_id=board.doing, position=1)

    assert db_cards(session, board.todo) == [("b", 0)]
    assert db_cards(session, board.doing) == [("x", 0), ("a", 1), ("y", 2)]


def test_move_to_empty_column(api, board, session):
    (a,) = api.seed(board.id, board.todo, "a")

    assert api.patch(a, column_id=board.done, position=0).json()["position"] == 0
    assert db_cards(session, board.todo) == []
    assert db_cards(session, board.done) == [("a", 0)]


def test_reorder_within_column(api, board, session):
    a, b, c, d = api.seed(board.id, board.todo, "a", "b", "c", "d")

    api.patch(a, position=2)
    assert db_cards(session, board.todo) == [("b", 0), ("c", 1), ("a", 2), ("d", 3)]

    api.patch(d, position=0)
    assert db_cards(session, board.todo) == [("d", 0), ("b", 1), ("c", 2), ("a", 3)]


def test_reorder_past_end_is_422_and_changes_nothing(api, board, session):
    a, b = api.seed(board.id, board.todo, "a", "b")

    response = api.patch(a, position=2)

    assert response.status_code == 422
    assert response.json()["detail"] == "position must be between 0 and 1"
    assert db_cards(session, board.todo) == [("a", 0), ("b", 1)]


def test_move_to_same_column_with_same_position_is_noop(api, board, session):
    a, b = api.seed(board.id, board.todo, "a", "b")

    api.patch(b, column_id=board.todo, position=1)

    assert db_cards(session, board.todo) == [("a", 0), ("b", 1)]


def test_move_and_edit_in_one_request(api, board, session):
    (a,) = api.seed(board.id, board.todo, "a")

    body = api.patch(a, title="done!", column_id=board.done).json()

    assert (body["title"], body["column_id"], body["position"]) == ("done!", board.done, 0)


# --- delete --------------------------------------------------------------------


def test_delete_renumbers_and_cascades(api, board, session, client, owner):
    a, b, c = api.seed(board.id, board.todo, "a", "b", "c")
    child = api.create(board.id, title="child", column_id=board.doing, parent_card_id=b).json()["id"]
    client.post(f"/cards/{b}/checklist", json={"content": "i"}, headers=headers(owner))
    client.post(f"/cards/{b}/comments", json={"content": "c"}, headers=headers(owner))

    response = api.delete(b)

    assert response.status_code == 204
    assert response.content == b""
    session.expire_all()
    assert session.get(Card, b) is None
    assert db_cards(session, board.todo) == [("a", 0), ("c", 1)]
    assert session.get(Card, child).parent_card_id is None  # detached, not deleted
    assert session.scalar(select(ChecklistItem).where(ChecklistItem.card_id == b)) is None
    assert session.scalar(select(Comment).where(Comment.card_id == b)) is None


def test_delete_unknown_card_is_404(api):
    assert api.delete(999).status_code == 404


# --- labels --------------------------------------------------------------------


def test_label_create_list_rename(api, board, session):
    created = api.label(board.id, "  bug  ")

    assert created.status_code == 201
    assert created.json() == {"id": created.json()["id"], "board_id": board.id, "name": "bug"}
    api.label(board.id, "ui")
    assert [l["name"] for l in api.labels(board.id).json()] == ["bug", "ui"]

    renamed = api.rename_label(created.json()["id"], "defect")
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "defect"


def test_label_names_are_unique_per_board(api, board, other_board, outsider):
    bug = api.label(board.id, "bug").json()["id"]
    api.label(board.id, "ui")

    assert api.label(board.id, "bug").status_code == 409
    assert api.label(board.id, "bug").json() == {"detail": "A label with this name already exists"}
    assert api.rename_label(bug, "ui").status_code == 409
    assert api.rename_label(bug, "bug").status_code == 200  # same name is fine
    assert api.label(other_board.id, "bug", as_user=outsider).status_code == 201


@pytest.mark.parametrize("name", ["", "   ", "x" * 51])
def test_label_rejects_bad_name(api, board, name):
    assert api.label(board.id, name).status_code == 422


def test_attach_two_labels_then_detach_one(api, board, session):
    bug = api.label(board.id, "bug").json()["id"]
    ui = api.label(board.id, "ui").json()["id"]
    card_id = api.seed(board.id, board.todo, "x")[0]

    both = api.patch(card_id, label_ids=[bug, ui]).json()
    assert [l["id"] for l in both["labels"]] == [bug, ui]

    one = api.patch(card_id, label_ids=[ui]).json()
    assert [l["id"] for l in one["labels"]] == [ui]
    assert api.patch(card_id, label_ids=[]).json()["labels"] == []
    assert session.scalar(select(CardLabel).where(CardLabel.card_id == card_id)) is None


def test_duplicate_label_ids_are_collapsed(api, board):
    bug = api.label(board.id, "bug").json()["id"]
    card_id = api.seed(board.id, board.todo, "x")[0]

    assert [l["id"] for l in api.patch(card_id, label_ids=[bug, bug]).json()["labels"]] == [bug]


def test_deleting_a_label_removes_it_from_all_cards(api, board, session):
    bug = api.label(board.id, "bug").json()["id"]
    ui = api.label(board.id, "ui").json()["id"]
    a, b = api.seed(board.id, board.todo, "a", "b")
    api.patch(a, label_ids=[bug, ui])
    api.patch(b, label_ids=[bug])

    response = api.delete_label(bug)

    assert response.status_code == 204
    assert session.get(Label, bug) is None
    assert [l["id"] for l in api.get(a).json()["labels"]] == [ui]
    assert api.get(b).json()["labels"] == []
    assert [l["name"] for l in api.labels(board.id).json()] == ["ui"]


def test_label_unknown_ids_are_404(api):
    assert api.rename_label(999, "x").status_code == 404
    assert api.delete_label(999).status_code == 404


# --- membership ----------------------------------------------------------------


def test_member_can_do_everything(api, board, member):
    label = api.label(board.id, "bug", as_user=member).json()["id"]
    card = api.create(board.id, title="x", column_id=board.todo, label_ids=[label], as_user=member)
    assert card.status_code == 201
    card_id = card.json()["id"]

    assert api.list(board.id, as_user=member).status_code == 200
    assert api.get(card_id, as_user=member).status_code == 200
    assert api.patch(card_id, as_user=member, column_id=board.done).status_code == 200
    assert api.rename_label(label, "ui", as_user=member).status_code == 200
    assert api.delete(card_id, as_user=member).status_code == 204
    assert api.delete_label(label, as_user=member).status_code == 204


def test_non_member_is_rejected_on_every_endpoint(api, board, outsider, session):
    label = api.label(board.id, "bug").json()["id"]
    card_id = api.seed(board.id, board.todo, "secret")[0]

    assert api.create(board.id, title="x", column_id=board.todo, as_user=outsider).status_code == 404
    assert api.list(board.id, as_user=outsider).status_code == 404
    assert api.get(card_id, as_user=outsider).status_code == 404
    assert api.patch(card_id, title="x", as_user=outsider).status_code == 404
    assert api.delete(card_id, as_user=outsider).status_code == 404
    assert api.label(board.id, "x", as_user=outsider).status_code == 404
    assert api.labels(board.id, as_user=outsider).status_code == 404
    assert api.rename_label(label, "x", as_user=outsider).status_code == 404
    assert api.delete_label(label, as_user=outsider).status_code == 404
    session.expire_all()
    assert session.get(Card, card_id).title == "secret"
    assert session.get(Label, label) is not None
