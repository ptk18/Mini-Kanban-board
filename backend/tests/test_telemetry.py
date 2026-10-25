"""Logs, traces and metrics for the key journey, and the privacy rule that
nothing user-supplied reaches a log line (issue #44)."""

import json
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import telemetry
from app.models import Board, BoardMember, Card, Column, User
from app.services.auth import create_access_token

HEX32 = re.compile(r"^[0-9a-f]{32}$")
HEX16 = re.compile(r"^[0-9a-f]{16}$")


def request_logs(lines):
    return [line for line in lines if line.get("event") == "http.request"]


def test_request_log_has_the_shape_and_no_user_data(client: TestClient, log_lines, finished_spans):
    client.post("/auth/login", json={"email": "ada@example.com", "password": "hunter2hunter2"})

    entries = request_logs(log_lines())
    assert len(entries) == 1
    entry = entries[0]
    assert entry["level"] == "info"
    assert entry["timestamp"].endswith("Z")
    assert entry["http.request.method"] == "POST"
    assert entry["http.route"] == "/auth/login"
    assert entry["http.response.status_code"] == 401
    assert isinstance(entry["duration_ms"], float)
    assert HEX32.match(entry["trace_id"]) and HEX16.match(entry["span_id"])

    # Correlation: the log line's trace_id is the server span's trace_id.
    spans = [s for s in finished_spans() if s.name == "POST /auth/login"]
    assert spans, [s.name for s in finished_spans()]
    assert entry["trace_id"] in {format(s.context.trace_id, "032x") for s in spans}

    raw = str(entries)
    for secret in ("ada@example.com", "hunter2hunter2", "Bearer"):
        assert secret not in raw


def test_route_template_not_concrete_path_and_5xx_logged_as_error(
    client: TestClient, session: Session, log_lines
):
    user = User(email="x@example.com", password_hash="h", display_name="X")
    session.add(user)
    session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}
    client.get("/boards/123456", headers=headers)

    (entry,) = request_logs(log_lines())
    assert entry["http.route"] == "/boards/{board_id}"
    assert "123456" not in str(entry)
    assert entry["http.response.status_code"] == 404
    assert "Authorization" not in str(entry) and "Bearer" not in str(entry)


def test_unmatched_paths_are_logged_as_unmatched_not_verbatim(client: TestClient, log_lines):
    client.get("/no/such/route/ada@example.com")
    (entry,) = request_logs(log_lines())
    assert entry["http.route"] == "unmatched"
    assert entry["http.response.status_code"] == 404
    assert "ada@example.com" not in str(entry)


def test_health_is_not_logged_or_traced(client: TestClient, log_lines, finished_spans):
    client.get("/health")
    assert request_logs(log_lines()) == []
    assert [s for s in finished_spans() if "health" in s.name] == []


def test_sensitive_keys_are_redacted_even_when_passed_explicitly(log_lines):
    telemetry.log.info("debugging", password="pw", email="a@b.c", authorization="Bearer t", token="x", ok="fine")
    (entry,) = log_lines()
    assert entry["password"] == entry["email"] == entry["authorization"] == entry["token"] == "[redacted]"
    assert entry["ok"] == "fine"
    assert "pw" not in str(entry) and "a@b.c" not in str(entry)


def test_otel_log_records_carry_attributes_but_no_sensitive_keys(client: TestClient, log_lines, otel_logs):
    client.post("/auth/login", json={"email": "ada@example.com", "password": "hunter2hunter2"})
    records = [r.log_record for r in otel_logs.get_finished_logs()]
    http = [r for r in records if '"event": "http.request"' in str(r.body)]
    assert http, [r.body for r in records]
    body = json.loads(http[0].body)
    assert body["http.route"] == "/auth/login" and HEX32.match(body["trace_id"])
    attrs = dict(http[0].attributes)
    assert attrs["http.route"] == "/auth/login"
    assert attrs["http.response.status_code"] == 401
    assert set(attrs) & telemetry.SENSITIVE_KEYS == set()
    assert "ada@example.com" not in str(attrs)


@pytest.fixture
def board_with_cards(session: Session):
    user = User(email="owner@example.com", password_hash="h", display_name="Owner")
    session.add(user)
    session.flush()
    board = Board(name="B", owner_id=user.id)
    session.add(board)
    session.flush()
    session.add(BoardMember(board_id=board.id, user_id=user.id, role="owner"))
    todo = Column(board_id=board.id, name="To Do", position=0)
    done = Column(board_id=board.id, name="Done", position=1)
    session.add_all([todo, done])
    session.flush()
    a = Card(board_id=board.id, column_id=todo.id, title="A", position=0)
    b = Card(board_id=board.id, column_id=todo.id, title="B", position=1)
    session.add_all([a, b])
    session.commit()
    return user, board, todo, done, a, b


def test_card_move_increments_the_counter_and_logs_ids_only(
    client: TestClient, board_with_cards, metric_value, log_lines
):
    user, board, todo, done, a, b = board_with_cards
    headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}
    before = metric_value("kanban_card_moves")

    # Reorder inside the column: not a move.
    assert client.patch(f"/cards/{a.id}", json={"position": 1}, headers=headers).status_code == 200
    assert metric_value("kanban_card_moves") == before

    # Change column: a move.
    assert client.patch(f"/cards/{a.id}", json={"column_id": done.id}, headers=headers).status_code == 200
    assert metric_value("kanban_card_moves") == before + 1

    moved = [line for line in log_lines() if line.get("event") == "card.moved"]
    assert len(moved) == 1
    assert moved[0]["card_id"] == a.id
    assert moved[0]["from_column_id"] == todo.id and moved[0]["to_column_id"] == done.id
    assert HEX32.match(moved[0]["trace_id"])
    assert "title" not in moved[0] and '"A"' not in str(moved[0])


def test_request_metrics_are_recorded_by_route_and_status(client: TestClient, metrics_reader):
    client.get("/boards")  # 401, no token
    data = metrics_reader.get_metrics_data()
    names = {m.name for rm in data.resource_metrics for sm in rm.scope_metrics for m in sm.metrics}
    assert {"kanban_http_requests", "kanban_http_request_duration"} <= names
    points = [
        p
        for rm in data.resource_metrics for sm in rm.scope_metrics for m in sm.metrics
        if m.name == "kanban_http_requests"
        for p in m.data.data_points
    ]
    assert any(
        dict(p.attributes) == {"http.request.method": "GET", "http.route": "/boards", "http.response.status_code": 401}
        for p in points
    )


def test_otlp_setup_is_a_no_op_without_the_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert telemetry.setup_otlp_telemetry(None, None) is False


def test_resource_names_the_service_and_version(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "abc123")
    monkeypatch.setenv("APP_ENV", "test")
    attrs = telemetry.resource().attributes
    assert attrs["service.name"] == "mini-kanban-api"
    assert attrs["service.version"] == "abc123"
    assert attrs["deployment.environment.name"] == "test"
