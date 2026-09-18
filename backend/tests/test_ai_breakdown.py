import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import BoardMember, Card, User
from app.services.ai import AIError
from app.services.auth import create_access_token


def make_user(session: Session, email: str) -> User:
    user = User(email=email, password_hash="not-a-real-hash", display_name="x")
    session.add(user)
    session.commit()
    return user


def headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def snapshot(session: Session, card_id: int) -> dict:
    session.expire_all()
    card = session.get(Card, card_id)
    return {c.name: getattr(card, c.name) for c in Card.__table__.columns}

TASKS = [
    {"title": "Write the migration", "description": "Add the column."},
    {"title": "Update the API", "description": "Expose it."},
    {"title": "Ship it", "description": ""},
]
BREAKDOWN_REPLY = {"text": "Three steps.", "tasks": TASKS}
PROPOSAL = {
    "text": "A login fix due Friday.",
    "title": "Fix login redirect",
    "description": "Users land on /404 after login.",
    "priority": "high",
    "due_date": "2026-09-25T00:00:00+02:00",
}


def card_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Card))


@pytest.fixture
def owner(session: Session) -> User:
    return make_user(session, "owner@example.com")


@pytest.fixture
def board(client: TestClient, owner: User) -> dict:
    return client.post("/boards", json={"name": "Roadmap"}, headers=headers(owner)).json()


@pytest.fixture
def parent(client: TestClient, session: Session, owner: User, board: dict) -> Card:
    body = {"title": "Add invites", "description": "Whole feature", "column_id": board["columns"][1]["id"], "priority": "high"}
    card_id = client.post(f"/boards/{board['id']}/cards", json=body, headers=headers(owner)).json()["id"]
    return session.get(Card, card_id)


@pytest.fixture
def api(client: TestClient, owner: User):
    class Api:
        def breakdown(self, card_id: int, as_user: User = owner):
            return client.post(f"/ai/card/{card_id}/breakdown", headers=headers(as_user))

        def apply(self, card_id: int, tasks, as_user: User = owner):
            return client.post(f"/ai/card/{card_id}/breakdown/apply", json={"tasks": tasks}, headers=headers(as_user))

        def create_task(self, board_id: int, text: str, as_user: User = owner):
            return client.post("/ai/create-task", json={"board_id": board_id, "text": text}, headers=headers(as_user))

    return Api()


# --- breakdown preview ---------------------------------------------------------------


def test_breakdown_preview_returns_tasks_and_creates_nothing(api, parent, session, fake_ai):
    fake_ai.reply = json.dumps(BREAKDOWN_REPLY)
    before = snapshot(session, parent.id)

    response = api.breakdown(parent.id)

    assert response.status_code == 200
    assert response.json() == BREAKDOWN_REPLY
    assert card_count(session) == 1
    assert snapshot(session, parent.id) == before
    assert "Title: Add invites" in fake_ai.prompts[0]
    assert "child tasks" in fake_ai.prompts[0]


def test_breakdown_preview_rejects_empty_or_oversized_list(api, parent, fake_ai):
    fake_ai.reply = json.dumps({"text": "x", "tasks": []})
    assert api.breakdown(parent.id).status_code == 502

    fake_ai.reply = json.dumps({"text": "x", "tasks": [{"title": f"t{i}"} for i in range(21)]})
    assert api.breakdown(parent.id).status_code == 502


def test_breakdown_preview_fills_missing_description(api, parent, fake_ai):
    fake_ai.reply = json.dumps({"text": "x", "tasks": [{"title": "Only a title"}]})
    assert api.breakdown(parent.id).json()["tasks"] == [{"title": "Only a title", "description": ""}]


def test_breakdown_preview_non_member_is_404(api, parent, session, fake_ai):
    outsider = make_user(session, "outsider@example.com")
    assert api.breakdown(parent.id, as_user=outsider).status_code == 404
    assert fake_ai.prompts == []


# --- breakdown apply -----------------------------------------------------------------


def test_apply_creates_children_under_parent_in_its_column(api, parent, session, client, owner):
    sibling = client.post(
        f"/boards/{parent.board_id}/cards",
        json={"title": "Existing", "column_id": parent.column_id},
        headers=headers(owner),
    ).json()
    edited = [{"title": "  Write the migration ", "description": "Add the column."}, {"title": "Ship it"}]

    response = api.apply(parent.id, edited)

    assert response.status_code == 201
    body = response.json()
    assert [c["title"] for c in body] == ["Write the migration", "Ship it"]
    assert [c["description"] for c in body] == ["Add the column.", ""]
    assert all(c["parent_card_id"] == parent.id for c in body)
    assert all(c["board_id"] == parent.board_id for c in body)
    assert all(c["column_id"] == parent.column_id for c in body)
    assert all(c["priority"] == "medium" for c in body)
    assert [c["position"] for c in body] == [2, 3]  # after parent (0) and sibling (1)
    session.expire_all()
    assert card_count(session) == 4
    assert sorted(child.title for child in session.get(Card, parent.id).children) == ["Ship it", "Write the migration"]
    assert session.get(Card, sibling["id"]).position == 1


def test_apply_does_not_call_the_model(api, parent, fake_ai):
    api.apply(parent.id, TASKS)
    assert fake_ai.prompts == []


def test_apply_works_without_gemini_configured(api, parent, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert api.apply(parent.id, TASKS).status_code == 201


def test_apply_children_show_up_in_parent_detail_and_can_be_nested_no_further_than_data_allows(api, parent, client, owner):
    child_id = api.apply(parent.id, [{"title": "child"}]).json()[0]["id"]
    grandchild = api.apply(child_id, [{"title": "grandchild"}]).json()[0]
    assert grandchild["parent_card_id"] == child_id


@pytest.mark.parametrize(
    "tasks",
    [[], [{"title": ""}], [{"title": "x" * 201}], [{"description": "no title"}],
     [{"title": "t"}] * 21, [{"title": "t", "description": "x" * 5001}]],
)
def test_apply_rejects_invalid_lists_and_creates_nothing(api, parent, session, tasks):
    assert api.apply(parent.id, tasks).status_code == 422
    assert card_count(session) == 1


def test_apply_non_member_is_404_and_creates_nothing(api, parent, session):
    outsider = make_user(session, "outsider@example.com")
    assert api.apply(parent.id, TASKS, as_user=outsider).status_code == 404
    assert card_count(session) == 1


def test_apply_member_can(api, parent, session):
    member = make_user(session, "member@example.com")
    session.add(BoardMember(board_id=parent.board_id, user_id=member.id, role="member"))
    session.commit()
    assert api.apply(parent.id, TASKS, as_user=member).status_code == 201


def test_apply_unknown_card_is_404(api):
    assert api.apply(999, TASKS).status_code == 404


# --- create-task -----------------------------------------------------------------------


def test_create_task_returns_proposal_and_saves_nothing(api, board, session, fake_ai):
    fake_ai.reply = json.dumps(PROPOSAL)

    response = api.create_task(board["id"], "  Fix the login redirect bug, it's urgent, by Friday ")

    assert response.status_code == 200
    body = response.json()
    assert body == {**PROPOSAL, "due_date": "2026-09-24T22:00:00Z"}  # normalised to UTC
    assert card_count(session) == 0
    (prompt,) = fake_ai.prompts
    assert "Fix the login redirect bug, it's urgent, by Friday" in prompt
    assert "today (" in prompt and "JSON" in prompt


def test_create_task_proposal_can_be_posted_as_a_card(api, board, session, fake_ai, client, owner):
    fake_ai.reply = json.dumps(PROPOSAL)
    proposal = api.create_task(board["id"], "anything").json()
    proposal.pop("text")

    created = client.post(
        f"/boards/{board['id']}/cards",
        json={**proposal, "column_id": board["columns"][0]["id"]},
        headers=headers(owner),
    )

    assert created.status_code == 201
    assert created.json()["title"] == PROPOSAL["title"]
    assert created.json()["due_date"] == "2026-09-24T22:00:00Z"


def test_create_task_defaults_when_model_omits_optional_fields(api, board, fake_ai):
    fake_ai.reply = json.dumps({"text": "x", "title": "Just a title"})

    body = api.create_task(board["id"], "just a title").json()

    assert body == {"text": "x", "title": "Just a title", "description": "", "priority": "medium", "due_date": None}


@pytest.mark.parametrize(
    "reply",
    [{"text": "x", "title": ""}, {"text": "x", "title": "t", "priority": "urgent"},
     {"text": "x", "title": "t", "due_date": "next friday"}, {"text": "x"}],
)
def test_create_task_rejects_bad_proposals(api, board, session, fake_ai, reply):
    fake_ai.reply = json.dumps(reply)
    assert api.create_task(board["id"], "x").status_code == 502
    assert card_count(session) == 0


@pytest.mark.parametrize("text", ["", "   ", "x" * 2001])
def test_create_task_rejects_bad_text(api, board, fake_ai, text):
    assert api.create_task(board["id"], text).status_code == 422
    assert fake_ai.prompts == []


def test_create_task_non_member_is_404_before_the_model_is_called(api, board, session, fake_ai):
    outsider = make_user(session, "outsider@example.com")
    assert api.create_task(board["id"], "x", as_user=outsider).status_code == 404
    assert api.create_task(999, "x").status_code == 404
    assert fake_ai.prompts == []


def test_create_task_provider_error_is_502(api, board, fake_ai):
    fake_ai.reply = AIError("down")
    assert api.create_task(board["id"], "x").status_code == 502


def test_create_task_without_key_is_503(api, board, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert api.create_task(board["id"], "x").status_code == 503


def test_create_task_requires_token(client, board):
    assert client.post("/ai/create-task", json={"board_id": board["id"], "text": "x"}).status_code == 401
