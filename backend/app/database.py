"""Database engine, session factory and declarative base.

This module must not import ``app.models`` at top level: the models import
``Base`` from here, so the import would be circular. Whatever calls
``create_all`` imports ``app.models`` first so every table is registered.
"""

import os
from collections.abc import Generator
from datetime import datetime, timezone

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

DEFAULT_DATABASE_URL = "sqlite:///./mini_kanban.db"
IN_MEMORY_URLS = frozenset({"sqlite://", "sqlite:///:memory:"})


def utcnow() -> datetime:
    """Current UTC time as a naive datetime.

    SQLite has no timezone type and hands back naive datetimes, so storing
    naive UTC keeps what goes in equal to what comes out. Every timestamp
    default and every "is this overdue" comparison must use this helper.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
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


engine = make_engine(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    Base.metadata.create_all(engine)
