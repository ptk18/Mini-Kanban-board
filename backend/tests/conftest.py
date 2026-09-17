import os

# Must run before anything imports app.database: the module-level engine reads
# DATABASE_URL at import time, and the suite must never touch a file database.
os.environ.setdefault("DATABASE_URL", "sqlite://")

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: E402, F401  # registers every table on Base.metadata
from app.database import Base, make_engine  # noqa: E402


@pytest.fixture
def session() -> Iterator[Session]:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()
