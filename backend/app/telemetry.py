"""Structured logs, traces and metrics for the API.

Three signals, one correlation key:

* **Logs** are JSON lines on stdout, one per request plus domain events,
  produced by structlog. Every line carries ``trace_id``/``span_id`` when a
  span is active, so a log line leads to its trace and back.
* **Traces** come from the FastAPI and SQLAlchemy instrumentations (one span
  per request, child spans per SQL statement).
* **Metrics** are OpenTelemetry instruments: request count and duration by
  route/method/status, and the business counter ``kanban_card_moves``.

Export happens only when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set (the OTLP
Collector in ``observability/``); the exporters read that variable
themselves. Without it the JSON logs still print and the metric/trace calls
are no-ops, so unit tests and ``uv run uvicorn`` are unaffected.

Privacy: nothing user-supplied is logged. Request logs hold method, route
template, status and duration — never headers, bodies, query strings or
e-mails — and ``redact`` drops any sensitive key that slips into an event.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections.abc import Awaitable, Callable
from typing import IO, Any

import structlog
from fastapi import FastAPI, Request, Response
from opentelemetry import metrics, trace
from opentelemetry._logs import SeverityNumber, set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import LogRecordExporter, SimpleLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricExporter, MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from sqlalchemy import Engine

from app.version import app_version

SERVICE = "mini-kanban-api"
METER_NAME = "mini-kanban"

# Keys that must never reach a log line, whatever the caller passed.
SENSITIVE_KEYS = frozenset(
    {"password", "password_hash", "authorization", "token", "access_token",
     "email", "cookie", "set-cookie", "secret", "jwt_secret", "api_key"}
)

_SEVERITY = {
    "debug": SeverityNumber.DEBUG, "info": SeverityNumber.INFO,
    "warning": SeverityNumber.WARN, "error": SeverityNumber.ERROR,
    "critical": SeverityNumber.FATAL,
}


def otlp_endpoint() -> str | None:
    return os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or None


def resource() -> Resource:
    return Resource.create(
        {
            SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", SERVICE),
            SERVICE_VERSION: app_version(),
            "deployment.environment.name": os.environ.get("APP_ENV", "local"),
        }
    )


# ----------------------------------------------------------------- metrics --

_meter = metrics.get_meter(METER_NAME)
# The instruments are created once against the API's proxy meter, so they
# keep working after a real MeterProvider is installed later.
REQUESTS = _meter.create_counter(
    "kanban_http_requests", description="HTTP requests served, by route, method and status."
)
REQUEST_DURATION = _meter.create_histogram(
    "kanban_http_request_duration", unit="ms", description="Request wall time in milliseconds."
)
CARD_MOVES = _meter.create_counter(
    "kanban_card_moves", description="Cards moved to another column (the key user journey)."
)


# ------------------------------------------------------------------- logs ---


def redact(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key in list(event_dict):
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = "[redacted]"
    return event_dict


def add_trace_context(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    ctx = trace.get_current_span().get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


class OTelLogExporterProcessor:
    """structlog processor that mirrors every event to an OpenTelemetry
    logger (so it reaches Loki through the Collector). The body is the same
    JSON line that goes to stdout, so a text search for a trace id finds it;
    the fields are also attached as attributes (Loki structured metadata) so
    they can be filtered as labels."""

    def __init__(self, provider: LoggerProvider):
        self._logger = provider.get_logger(SERVICE)

    def __call__(self, _logger: Any, method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        attributes = {
            k: v for k, v in event_dict.items()
            if k not in {"event", "timestamp", "level", "trace_id", "span_id"}
            and isinstance(v, (str, bool, int, float))
        }
        self._logger.emit(
            body=json.dumps(event_dict, default=str),
            severity_text=str(event_dict.get("level", "info")).upper(),
            severity_number=_SEVERITY.get(str(event_dict.get("level", "info")), SeverityNumber.INFO),
            attributes=attributes,
        )
        return event_dict


def configure_logging(stream: IO[str] | None = None, log_provider: LoggerProvider | None = None) -> None:
    """JSON lines to ``stream`` (stdout by default) with level, ISO-8601 UTC
    timestamp, trace context and redaction. ``log_provider`` additionally
    mirrors events to OpenTelemetry."""
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        add_trace_context,
        redact,
    ]
    if log_provider is not None:
        processors.append(OTelLogExporterProcessor(log_provider))
    processors.append(structlog.processors.JSONRenderer())
    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(file=stream or sys.stdout),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=False,
    )


log = structlog.get_logger()


# ---------------------------------------------------------------- tracing ---


def setup_telemetry(
    app: FastAPI,
    engine: Engine | None,
    *,
    span_exporter: SpanExporter,
    metric_reader: MetricReader,
    log_exporter: LogRecordExporter | None = None,
    log_stream: IO[str] | None = None,
) -> tuple[TracerProvider, MeterProvider, LoggerProvider | None]:
    """Install providers and instrument the app and the database engine.
    Tests pass in-memory exporters; production passes OTLP ones."""
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    res = resource()
    tracer_provider = TracerProvider(resource=res)
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    meter_provider = MeterProvider(resource=res, metric_readers=[metric_reader])
    trace.set_tracer_provider(tracer_provider)
    metrics.set_meter_provider(meter_provider)

    log_provider = None
    if log_exporter is not None:
        log_provider = LoggerProvider(resource=res)
        log_provider.add_log_record_processor(SimpleLogRecordProcessor(log_exporter))
        set_logger_provider(log_provider)
    configure_logging(stream=log_stream, log_provider=log_provider)

    # /health is probed every few seconds; keep it out of the traces.
    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=tracer_provider, meter_provider=meter_provider, excluded_urls="health"
    )
    if engine is not None:
        SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=tracer_provider)
    else:
        # No engine yet (tests build one per test): instrument every engine
        # created from now on.
        SQLAlchemyInstrumentor().instrument(tracer_provider=tracer_provider)
    return tracer_provider, meter_provider, log_provider


def setup_otlp_telemetry(app: FastAPI, engine: Engine) -> bool:
    """Production wiring: OTLP/HTTP exporters that read
    ``OTEL_EXPORTER_OTLP_ENDPOINT``. Returns False (and does nothing) when the
    variable is unset."""
    if not otlp_endpoint():
        return False
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    setup_telemetry(
        app,
        engine,
        span_exporter=OTLPSpanExporter(),
        metric_reader=PeriodicExportingMetricReader(
            OTLPMetricExporter(), export_interval_millis=10_000
        ),
        log_exporter=OTLPLogExporter(),
    )
    log.info("telemetry.enabled", endpoint=otlp_endpoint(), service=SERVICE)
    return True


def export_metrics_reader_factory(exporter: MetricExporter) -> MetricReader:
    return PeriodicExportingMetricReader(exporter, export_interval_millis=10_000)


# ------------------------------------------------------------- middleware ---


def request_logging_middleware(app: FastAPI) -> None:
    """One JSON log line and two metric points per request. Only the route
    *template* is recorded (``/boards/{board_id}``), never the concrete path,
    query string, headers or body."""

    @app.middleware("http")
    async def _log_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path == "/health":
            return await call_next(request)
        started = time.perf_counter()
        status_code = 500
        error: dict[str, str] = {}
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:  # re-raised below; recorded so the 500 has a cause in the logs
            error = {"error.type": type(exc).__name__, "error.message": str(exc)[:200]}
            raise
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            route = request.scope.get("route")
            attrs = {
                "http.request.method": request.method,
                # Only the template; an unmatched path is user-typed input and
                # unbounded, so it is never recorded.
                "http.route": getattr(route, "path", None) or "unmatched",
                "http.response.status_code": status_code,
            }
            REQUESTS.add(1, attrs)
            REQUEST_DURATION.record(duration_ms, attrs)
            (log.error if status_code >= 500 else log.info)(
                "http.request", duration_ms=duration_ms, **attrs, **error
            )
