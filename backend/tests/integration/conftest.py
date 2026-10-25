"""Integration tests: the real app against a real Postgres.

Set ``TEST_DATABASE_URL`` (``postgresql+psycopg://...``) to run them; without
it every test in this directory is skipped, so ``uv run pytest`` stays a
SQLite-only unit run. ``make test-integration`` starts the Compose database
and sets the variable.

The database is wiped and migrated to ``head`` once per module with Alembic
(the migrations are part of what is under test); between tests the tables
are truncated so each test starts empty but keeps the migrated schema.
"""

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

import app.models  # noqa: F401  # registers every table on Base.metadata
from app.database import ALEMBIC_INI, Base, get_db
from app.main import app as fastapi_app

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")


def pytest_collection_modifyitems(config, items):
    if TEST_DATABASE_URL:
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL not set; integration tests need Postgres")
    for item in items:
        if "tests/integration" in str(item.fspath).replace(os.sep, "/"):
            item.add_marker(skip)


def alembic_config(url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", url)
    return config


def wipe(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture(scope="module")
def pg_url() -> str:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    return TEST_DATABASE_URL


@pytest.fixture(scope="module")
def alembic_cfg(pg_url: str) -> Config:
    return alembic_config(pg_url)


@pytest.fixture(scope="module")
def pg_engine() -> Iterator[Engine]:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    wipe(engine)
    command.upgrade(alembic_config(TEST_DATABASE_URL), "head")
    yield engine
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine: Engine) -> Iterator[Session]:
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with pg_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    with Session(pg_engine) as db:
        yield db


@pytest.fixture
def pg_client(pg_session: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield pg_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()
