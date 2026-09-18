import os

# Must run before anything imports app.database: the module-level engine reads
# DATABASE_URL at import time, and the suite must never touch a file database.
os.environ.setdefault("DATABASE_URL", "sqlite://")
# Set unconditionally (not setdefault): the value is meaningless for tests and must
# not depend on the developer's shell. At least 32 characters, see get_jwt_secret.
os.environ["JWT_SECRET"] = "test-only-jwt-secret-not-for-production-0123456789"

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: E402, F401  # registers every table on Base.metadata
import app.services.ai  # noqa: E402
import app.services.auth  # noqa: E402
from app.database import Base, get_db, make_engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


@pytest.fixture
def session() -> Iterator[Session]:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    # No `with`: the lifespan is not run, the schema comes from the session fixture.
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def fast_bcrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    # Cost 12 is ~0.18 s per hash; cost 4 keeps the suite fast. One test undoes
    # this to exercise the production cost.
    monkeypatch.setattr(app.services.auth, "BCRYPT_ROUNDS", 4)


class FakeAI:
    """Stand-in for app.services.ai.AIClient: records prompts and replies
    with whatever the test queued (a string, or an exception to raise)."""

    def __init__(self, reply: str = "{}"):
        self.reply = reply
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


@pytest.fixture
def fake_ai() -> Iterator[FakeAI]:
    fake = FakeAI()
    fastapi_app.dependency_overrides[app.services.ai.get_ai_client] = lambda: fake
    yield fake
    fastapi_app.dependency_overrides.pop(app.services.ai.get_ai_client, None)
