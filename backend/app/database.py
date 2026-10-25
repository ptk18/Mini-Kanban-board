"""Database engine, session factory and declarative base.

This module must not import ``app.models`` at top level: the models import
``Base`` from here, so the import would be circular. Whatever calls
``create_all`` imports ``app.models`` first so every table is registered.

Two databases are supported. SQLite is the zero-setup default for local
development and the unit suite; Postgres (``postgresql+psycopg://...``) is
what Docker Compose and production use. The schema reaches Postgres through
Alembic migrations (``alembic/``); SQLite keeps ``create_all`` because a
throwaway file or in-memory database has nothing to migrate.
"""

import os
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

DEFAULT_DATABASE_URL = "sqlite:///./mini_kanban.db"
IN_MEMORY_URLS = frozenset({"sqlite://", "sqlite:///:memory:"})
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def is_sqlite_url(url: str) -> bool:
    return make_url(url).get_backend_name() == "sqlite"


def utcnow() -> datetime:
    """Current UTC time as a naive datetime.

    Timestamps are stored without a timezone on both backends (SQLite has no
    timezone type; Postgres gets ``TIMESTAMP WITHOUT TIME ZONE``), so storing
    naive UTC keeps what goes in equal to what comes out. Every timestamp
    default and every "is this overdue" comparison must use this helper.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    if not is_sqlite_url(url):
        # pool_pre_ping drops connections Postgres closed (restart, idle
        # timeout) instead of handing them to a request.
        return create_engine(url, pool_pre_ping=True)

    kwargs: dict[str, object] = {"connect_args": {"check_same_thread": False}}
    if url in IN_MEMORY_URLS:
        # The default SingletonThreadPool gives each thread its own empty
        # in-memory database; StaticPool shares one connection across threads.
        kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
        # SQLite ignores foreign keys unless every connection opts in.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


engine = make_engine(database_url())
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    Base.metadata.create_all(engine)


def run_migrations() -> None:
    """Bring the configured database to the latest Alembic revision."""
    from alembic import command
    from alembic.config import Config

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", str(engine.url.render_as_string(hide_password=False)))
    command.upgrade(config, "head")


def prepare_database() -> None:
    """Make the schema match the models: ``create_all`` on SQLite, Alembic
    migrations everywhere else. Called from the app lifespan and the seed."""
    if is_sqlite_url(str(engine.url)):
        create_all()
    else:
        run_migrations()
