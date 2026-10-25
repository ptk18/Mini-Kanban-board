import os

# Must run before anything imports app.database: the module-level engine reads
# DATABASE_URL at import time, and the suite must never touch a file database.
os.environ.setdefault("DATABASE_URL", "sqlite://")
# Set unconditionally (not setdefault): the value is meaningless for tests and must
# not depend on the developer's shell. At least 32 characters, see get_jwt_secret.
os.environ["JWT_SECRET"] = "test-only-jwt-secret-not-for-production-0123456789"

from collections.abc import Callable, Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import io  # noqa: E402

from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter  # noqa: E402
from opentelemetry.sdk.metrics.export import InMemoryMetricReader  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter  # noqa: E402

import app.models  # noqa: E402, F401  # registers every table on Base.metadata
import app.services.ai  # noqa: E402
import app.services.auth  # noqa: E402
from app import telemetry  # noqa: E402
from app.database import Base, get_db, make_engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402

# The whole suite runs instrumented, as production does, but every signal
# lands in memory: spans, metric points and OTel log records are inspectable
# through the fixtures below, and the JSON log lines go to a StringIO.
SPANS = InMemorySpanExporter()
METRICS = InMemoryMetricReader()
OTEL_LOGS = InMemoryLogRecordExporter()
LOG_STREAM = io.StringIO()
TRACER_PROVIDER, METER_PROVIDER, LOG_PROVIDER = telemetry.setup_telemetry(
    fastapi_app, engine=None, span_exporter=SPANS, metric_reader=METRICS,
    log_exporter=OTEL_LOGS, log_stream=LOG_STREAM,
)


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


@pytest.fixture
def log_lines() -> Iterator[Callable[[], list[dict]]]:
    """Fresh JSON log capture for one test; call it to get the parsed lines."""
    import json

    buf = io.StringIO()
    telemetry.configure_logging(stream=buf, log_provider=LOG_PROVIDER)
    # Flush before clearing, or spans from earlier tests arrive after the clear.
    TRACER_PROVIDER.force_flush()
    OTEL_LOGS.clear()
    SPANS.clear()

    def read() -> list[dict]:
        return [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]

    yield read
    telemetry.configure_logging(stream=LOG_STREAM, log_provider=LOG_PROVIDER)


@pytest.fixture
def finished_spans() -> Callable[[], list]:
    def read() -> list:
        TRACER_PROVIDER.force_flush()
        return list(SPANS.get_finished_spans())

    return read


@pytest.fixture
def metric_value() -> Callable[[str], float]:
    """Cumulative value of a counter by instrument name (0 when never recorded)."""

    def read(name: str) -> float:
        total = 0.0
        data = METRICS.get_metrics_data()
        for rm in (data.resource_metrics if data else []):
            for sm in rm.scope_metrics:
                for metric in sm.metrics:
                    if metric.name == name:
                        total += sum(p.value for p in metric.data.data_points)
        return total

    return read


@pytest.fixture
def otel_logs() -> InMemoryLogRecordExporter:
    return OTEL_LOGS


@pytest.fixture
def metrics_reader() -> InMemoryMetricReader:
    return METRICS
