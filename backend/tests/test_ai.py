import io
import json
import urllib.error

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.services.ai as ai_module
from app.main import app as fastapi_app
from app.models import BoardMember, Card, User
from app.services.ai import AIError, GeminiClient, extract_text, get_ai_client, parse_json_reply
from app.services.auth import create_access_token

ACTIONS = ["improve", "prioritize", "estimate", "summarize"]
REPLIES = {
    "improve": {"text": "Made it specific.", "title": "Fix login redirect", "description": "Steps..."},
    "prioritize": {"text": "Due tomorrow.", "priority": "high"},
    "estimate": {"text": "Two files.", "size": "Small", "time_estimate": "2 hours"},
    "summarize": {"text": "Login sends users to the wrong page."},
}


class FakeAI:
    """Records prompts and replies with whatever the test queued."""

    def __init__(self, reply: str = "{}"):
        self.reply = reply
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


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


@pytest.fixture
def owner(session: Session) -> User:
    return make_user(session, "owner@example.com")


@pytest.fixture
def card(client: TestClient, session: Session, owner: User) -> Card:
    board = client.post("/boards", json={"name": "Roadmap"}, headers=headers(owner)).json()
    body = {
        "title": "Fix login",
        "description": "Users land on /404 after login",
        "column_id": board["columns"][0]["id"],
        "priority": "medium",
        "due_date": "2026-03-04T05:06:00Z",
    }
    card_id = client.post(f"/boards/{board['id']}/cards", json=body, headers=headers(owner)).json()["id"]
    return session.get(Card, card_id)


@pytest.fixture
def fake_ai():
    fake = FakeAI()
    fastapi_app.dependency_overrides[get_ai_client] = lambda: fake
    yield fake
    fastapi_app.dependency_overrides.pop(get_ai_client, None)


@pytest.fixture
def call(client: TestClient, owner: User):
    def run(action: str, card_id: int, as_user: User = owner):
        return client.post(f"/ai/card/{card_id}/{action}", headers=headers(as_user))

    return run


# --- each action -------------------------------------------------------------------


@pytest.mark.parametrize("action", ACTIONS)
def test_action_returns_preview_and_leaves_card_unchanged(call, card, session, fake_ai, action):
    fake_ai.reply = json.dumps(REPLIES[action])
    before = snapshot(session, card.id)

    response = call(action, card.id)

    assert response.status_code == 200
    assert response.json() == REPLIES[action]
    assert snapshot(session, card.id) == before
    assert len(fake_ai.prompts) == 1


@pytest.mark.parametrize("action", ACTIONS)
def test_prompt_contains_only_the_cards_fields(call, card, fake_ai, action):
    fake_ai.reply = json.dumps(REPLIES[action])

    call(action, card.id)

    (prompt,) = fake_ai.prompts
    assert "Title: Fix login" in prompt
    assert "Description: Users land on /404 after login" in prompt
    assert "Priority: medium" in prompt
    assert "Due date: 2026-03-04T05:06 UTC" in prompt
    assert "JSON" in prompt
    assert "Roadmap" not in prompt  # board name is not card context


def test_prompt_marks_empty_description_and_missing_due_date(call, card, session, fake_ai):
    card.description = ""
    card.due_date = None
    session.commit()
    fake_ai.reply = json.dumps(REPLIES["summarize"])

    call("summarize", card.id)

    assert "Description: (empty)" in fake_ai.prompts[0]
    assert "Due date: none" in fake_ai.prompts[0]


def test_improve_gives_title_and_description_to_apply_later(call, card, fake_ai):
    fake_ai.reply = json.dumps(REPLIES["improve"])
    body = call("improve", card.id).json()
    assert body.keys() == {"text", "title", "description"}


def test_prioritize_rejects_unknown_priority(call, card, session, fake_ai):
    fake_ai.reply = json.dumps({"text": "x", "priority": "urgent"})
    before = snapshot(session, card.id)

    response = call("prioritize", card.id)

    assert response.status_code == 502
    assert "expected shape" in response.json()["detail"]
    assert snapshot(session, card.id) == before


def test_estimate_rejects_unknown_size(call, card, fake_ai):
    fake_ai.reply = json.dumps({"text": "x", "size": "Huge", "time_estimate": "1 day"})
    assert call("estimate", card.id).status_code == 502


def test_fenced_json_reply_is_accepted(call, card, fake_ai):
    fake_ai.reply = "```json\n" + json.dumps(REPLIES["summarize"]) + "\n```"
    assert call("summarize", card.id).json() == REPLIES["summarize"]


def test_extra_keys_in_reply_are_dropped(call, card, fake_ai):
    fake_ai.reply = json.dumps({**REPLIES["summarize"], "confidence": 0.9})
    assert call("summarize", card.id).json() == REPLIES["summarize"]


# --- failures ------------------------------------------------------------------------


def test_non_json_reply_is_502(call, card, fake_ai):
    fake_ai.reply = "Sure! Here is a summary."

    response = call("summarize", card.id)

    assert response.status_code == 502
    assert response.json() == {"detail": "AI reply is not valid JSON"}


def test_provider_error_is_502(call, card, fake_ai):
    fake_ai.reply = AIError("Gemini returned HTTP 429")

    response = call("summarize", card.id)

    assert response.status_code == 502
    assert response.json() == {"detail": "Gemini returned HTTP 429"}


def test_missing_api_key_is_503(call, card, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    response = call("summarize", card.id)

    assert response.status_code == 503
    assert response.json() == {"detail": "AI is not configured: set GEMINI_API_KEY"}


def test_non_member_is_404_before_the_model_is_called(call, card, session, fake_ai):
    outsider = make_user(session, "outsider@example.com")

    assert call("summarize", card.id, as_user=outsider).status_code == 404
    assert fake_ai.prompts == []


def test_member_can_call(call, card, session, fake_ai):
    member = make_user(session, "member@example.com")
    session.add(BoardMember(board_id=card.board_id, user_id=member.id, role="member"))
    session.commit()
    fake_ai.reply = json.dumps(REPLIES["summarize"])

    assert call("summarize", card.id, as_user=member).status_code == 200


def test_unknown_card_is_404(call, fake_ai):
    assert call("summarize", 999).status_code == 404


def test_requires_token(client, card):
    assert client.post(f"/ai/card/{card.id}/summarize").status_code == 401


# --- service helpers ---------------------------------------------------------------


@pytest.mark.parametrize(
    "reply",
    ['{"a": 1}', '```json\n{"a": 1}\n```', '```\n{"a": 1}\n```', '  {"a": 1}  '],
)
def test_parse_json_reply_accepts_fenced_and_padded(reply):
    assert parse_json_reply(reply) == {"a": 1}


@pytest.mark.parametrize("reply", ["", "nope", "[1]", "```json\n```"])
def test_parse_json_reply_rejects_unusable(reply):
    with pytest.raises(AIError):
        parse_json_reply(reply)


def test_extract_text_joins_parts():
    payload = {"candidates": [{"content": {"parts": [{"text": "{\"a\":"}, {"text": " 1}"}]}}]}
    assert extract_text(payload) == '{"a": 1}'


@pytest.mark.parametrize("payload", [{}, {"candidates": []}, {"candidates": [{"content": {"parts": []}}]}])
def test_extract_text_rejects_empty(payload):
    with pytest.raises(AIError):
        extract_text(payload)


def test_gemini_client_posts_prompt_and_reads_reply(monkeypatch):
    seen = {}

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["headers"] = {k.lower(): v for k, v in request.header_items()}
        seen["body"] = json.loads(request.data)
        seen["timeout"] = timeout
        return FakeResponse(json.dumps(
            {"candidates": [{"content": {"parts": [{"text": '{"text": "hi"}'}]}}]}
        ).encode())

    monkeypatch.setattr(ai_module.urllib.request, "urlopen", fake_urlopen)

    reply = GeminiClient("secret-key", model="gemini-test").generate("PROMPT")

    assert reply == '{"text": "hi"}'
    assert seen["url"] == "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
    assert seen["headers"]["x-goog-api-key"] == "secret-key"
    assert "secret-key" not in seen["url"]
    assert seen["body"]["contents"][0]["parts"][0]["text"] == "PROMPT"
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert seen["timeout"] == 30


def test_gemini_client_maps_http_error(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(ai_module.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(AIError, match="HTTP 429"):
        GeminiClient("k").generate("x")


def test_gemini_client_maps_network_error(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("dns")

    monkeypatch.setattr(ai_module.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(AIError, match="request failed"):
        GeminiClient("k").generate("x")


def test_get_ai_client_reads_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-custom")

    client = get_ai_client()

    assert isinstance(client, GeminiClient)
    assert client._model == "gemini-custom"
