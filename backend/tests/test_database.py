from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import database
from app.database import get_db, make_engine, utcnow
from app.main import app as fastapi_app

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


@pytest.mark.parametrize("url", ["sqlite://", "sqlite:///:memory:"])
def test_make_engine_in_memory_uses_static_pool(url):
    engine = make_engine(url)
    try:
        assert isinstance(engine.pool, StaticPool)
    finally:
        engine.dispose()


def test_make_engine_enables_foreign_keys_on_every_connection():
    engine = make_engine("sqlite://")
    try:
        with engine.connect() as conn:
            assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
    finally:
        engine.dispose()


def test_module_engine_reads_database_url_from_conftest():
    assert str(database.engine.url) == "sqlite://"


def test_get_db_yields_session_and_closes_it():
    gen = get_db()
    db = next(gen)
    assert isinstance(db, Session)
    db.execute(text("SELECT 1"))
    assert db.in_transaction()

    with patch.object(db, "close", wraps=db.close) as close:
        with pytest.raises(StopIteration):
            next(gen)
    close.assert_called_once()
    assert not db.in_transaction()


def test_get_db_closes_session_when_request_raises():
    gen = get_db()
    db = next(gen)
    db.execute(text("SELECT 1"))

    with patch.object(db, "close", wraps=db.close) as close:
        with pytest.raises(RuntimeError):
            gen.throw(RuntimeError("request failed"))
    close.assert_called_once()
    assert not db.in_transaction()


def test_lifespan_creates_tables_and_health_still_works():
    with TestClient(fastapi_app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health").json() == {"status": "ok"}
        assert set(inspect(database.engine).get_table_names()) >= TABLE_NAMES


def test_lifespan_is_idempotent():
    with TestClient(fastapi_app):
        pass
    with TestClient(fastapi_app) as client:
        assert client.get("/health").status_code == 200


def test_only_expected_routes_are_exposed():
    with TestClient(fastapi_app) as client:
        paths = client.get("/openapi.json").json()["paths"]
    assert {path: set(ops) for path, ops in paths.items()} == {
        "/health": {"get"},
        "/auth/signup": {"post"},
        "/auth/login": {"post"},
        "/auth/me": {"get"},
        "/boards": {"get", "post"},
        "/boards/{board_id}": {"get", "patch", "delete"},
        "/boards/{board_id}/columns": {"post"},
        "/boards/{board_id}/dashboard": {"get"},
        "/boards/{board_id}/invite": {"post"},
        "/invite/{token}/join": {"post"},
        "/boards/{board_id}/members": {"get", "post"},
        "/boards/{board_id}/members/{user_id}": {"delete"},
        "/columns/{column_id}": {"patch", "delete"},
        "/boards/{board_id}/labels": {"get", "post"},
        "/labels/{label_id}": {"patch", "delete"},
        "/boards/{board_id}/cards": {"get", "post"},
        "/cards/{card_id}": {"get", "patch", "delete"},
        "/ai/card/{card_id}/improve": {"post"},
        "/ai/card/{card_id}/prioritize": {"post"},
        "/ai/card/{card_id}/estimate": {"post"},
        "/ai/card/{card_id}/summarize": {"post"},
        "/ai/card/{card_id}/breakdown": {"post"},
        "/ai/card/{card_id}/breakdown/apply": {"post"},
        "/ai/create-task": {"post"},
        "/cards/{card_id}/checklist": {"get", "post"},
        "/checklist/{item_id}": {"patch", "delete"},
        "/cards/{card_id}/comments": {"get", "post"},
        "/comments/{comment_id}": {"patch", "delete"},
    }


def test_utcnow_is_naive_utc():
    now = utcnow()
    assert now.tzinfo is None
    expected = datetime.now(timezone.utc).replace(tzinfo=None)
    assert abs((expected - now).total_seconds()) < 5


POSTGRES_URL = "postgresql+psycopg://kanban:secret@db.invalid:5432/kanban"


def test_is_sqlite_url_distinguishes_backends():
    assert database.is_sqlite_url("sqlite://")
    assert database.is_sqlite_url("sqlite:///./mini_kanban.db")
    assert not database.is_sqlite_url(POSTGRES_URL)


def test_make_engine_postgres_has_no_sqlite_specific_setup():
    # create_engine does not connect, so an unreachable host is fine here.
    engine = make_engine(POSTGRES_URL)
    try:
        assert engine.dialect.name == "postgresql"
        assert not isinstance(engine.pool, StaticPool)
        assert engine.pool._pre_ping is True
        # The PRAGMA listener would raise on psycopg; it must not be registered.
        from sqlalchemy import event

        assert not event.contains(engine, "connect", database.make_engine)
    finally:
        engine.dispose()


def test_prepare_database_uses_create_all_on_sqlite(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(database, "create_all", lambda: calls.append("create_all"))
    monkeypatch.setattr(database, "run_migrations", lambda: calls.append("migrate"))
    database.prepare_database()
    assert calls == ["create_all"]


def test_prepare_database_runs_migrations_elsewhere(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(database, "create_all", lambda: calls.append("create_all"))
    monkeypatch.setattr(database, "run_migrations", lambda: calls.append("migrate"))
    monkeypatch.setattr(database, "engine", make_engine(POSTGRES_URL))
    database.prepare_database()
    assert calls == ["migrate"]


def test_alembic_ini_has_no_hardcoded_url():
    text_ = database.ALEMBIC_INI.read_text()
    assert database.ALEMBIC_INI.exists()
    assert "sqlalchemy.url =" not in text_
