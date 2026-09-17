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


def test_only_health_route_is_exposed():
    with TestClient(fastapi_app) as client:
        paths = client.get("/openapi.json").json()["paths"]
    assert paths.keys() == {"/health"}
    assert paths["/health"].keys() == {"get"}


def test_utcnow_is_naive_utc():
    now = utcnow()
    assert now.tzinfo is None
    expected = datetime.now(timezone.utc).replace(tzinfo=None)
    assert abs((expected - now).total_seconds()) < 5
