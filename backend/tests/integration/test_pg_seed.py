"""The demo seed works on Postgres and stays idempotent there."""

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Board, Card, User

SEED_PATH = Path(__file__).resolve().parents[2] / "scripts" / "seed.py"


@pytest.fixture(scope="module")
def seed_module():
    spec = importlib.util.spec_from_file_location("seed_pg", SEED_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["seed_pg"] = module
    spec.loader.exec_module(module)
    return module


def count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_seed_is_idempotent_on_postgres(pg_session: Session, seed_module):
    first = seed_module.seed(pg_session)
    second = seed_module.seed(pg_session)

    assert first["users"] == 3 and first["cards"] == 14
    assert sum(second.values()) == 0
    assert count(pg_session, User) == 3
    assert count(pg_session, Board) == 1
    assert count(pg_session, Card) == 14


def test_seed_accounts_can_log_in(pg_client: TestClient, pg_session: Session, seed_module):
    seed_module.seed(pg_session)
    r = pg_client.post(
        "/auth/login", json={"email": "ada@example.com", "password": seed_module.DEMO_PASSWORD}
    )
    assert r.status_code == 200
    boards = pg_client.get(
        "/boards", headers={"Authorization": f"Bearer {r.json()['access_token']}"}
    ).json()
    assert [(b["name"], b["role"]) for b in boards] == [(seed_module.BOARD_NAME, "owner")]
