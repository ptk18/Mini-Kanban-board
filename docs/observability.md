# Observability

The API emits three signals that share one key, the **trace id**, so any one
of them leads to the other two:

| Signal | Produced by | Shipped via | Stored in | Looks like |
|---|---|---|---|---|
| Structured logs | `structlog` → JSON lines on stdout, one per request plus domain events (`card.moved`) | OTLP logs → Collector → Loki `/otlp` | Loki | `{"event":"http.request","http.route":"/cards/{card_id}","http.response.status_code":200,"duration_ms":4.1,"trace_id":"8f…","span_id":"3a…","timestamp":"…Z","level":"info"}` |
| Traces | OpenTelemetry FastAPI + SQLAlchemy instrumentation: one server span per request, a child span per SQL statement | OTLP → Collector → Tempo | Tempo | `PATCH /cards/{card_id}` → `UPDATE cards …` |
| Metrics | `kanban_http_requests` (counter), `kanban_http_request_duration` (ms histogram), both by route/method/status; `kanban_card_moves` (counter); `httpcheck_status` from the Collector's own probe of `/health` | OTLP → Collector → Prometheus exporter, scraped every 10 s | Prometheus | `kanban_http_requests_total{http_route="/cards/{card_id}",http_response_status_code="200"}` |

All of it is in `backend/app/telemetry.py` (~150 lines) and switched on by one
variable, `OTEL_EXPORTER_OTLP_ENDPOINT`. Without it the JSON logs still print
and the metric and trace calls are no-ops, which is how unit tests and the
plain `uv run uvicorn` run.

## Run it

```sh
make observe        # app stack + observability stack, built and healthy
make seed           # demo board, then click around at http://localhost:3000
make observe-down
```

| UI | URL |
|---|---|
| Grafana (anonymous admin, local only) | http://localhost:3001/d/mini-kanban |
| Prometheus | http://localhost:9090 |
| Alertmanager | http://localhost:9093 |

Everything lives in [`observability/`](../observability/):
`compose.yaml` (layered on the root `docker-compose.yml`), `collector.yaml`,
`prometheus.yml`, `alerts.yaml`, `alertmanager.yml`, `loki.yaml`,
`tempo.yaml`, `grafana/` (datasource and dashboard provisioning) and
`dashboards/mini-kanban.json`. Image versions are pinned.

## The key journey: moving a card

`PATCH /cards/{id}` with a new `column_id` is the action the board exists
for. It is instrumented three ways:

1. the request span (plus the SQL spans under it) in Tempo;
2. the `http.request` log line and a `card.moved` log line carrying
   `card_id`, `board_id`, `from_column_id`, `to_column_id` and the same
   `trace_id`;
3. `kanban_card_moves_total` goes up by one (reorders inside a column do
   not count).

The dashboard shows the move rate next to request rate, p95 latency, 5xx
ratio and the `/health` probe, so a regression in the journey is visible as
"moves stopped while errors rose".

## From a log line to its trace and back

1. In Grafana, open the dashboard's **API logs** panel (or *Explore → Loki*,
   query `{service_name="mini-kanban-api"} |= "card.moved"`).
2. Expand a line. `trace_id` is a derived field; click **View trace**.
3. Tempo opens the whole request: the server span, every SQL statement, and
   their timings.
4. From any span, **Logs for this span** runs the reverse query in Loki
   (`tracesToLogsV2` in the datasource provisioning), filtered by that trace
   id.

Without Grafana, the same correlation works by hand:

```sh
docker compose logs backend | grep '"card.moved"' | tail -1      # copy trace_id
curl -s "http://localhost:3200/api/traces/<trace_id>" | head -c 400
```

## What is deliberately not in the telemetry

- No e-mails, passwords, tokens, cookies or `Authorization` headers. Request
  logs record the **route template** (`/boards/{board_id}`), never the
  concrete path, query string, headers or body. `telemetry.redact` replaces
  any such key that a caller passes explicitly with `[redacted]`, and the
  Collector's `attributes/scrub` processor deletes the same keys again
  before anything is stored. `tests/test_telemetry.py` asserts a login
  request leaves neither the e-mail nor the password in any log line or log
  record.
- `/health` is excluded from traces and request logs (it is probed every
  10 s by the Collector and by Docker; it would be most of the data).
- Card titles, descriptions and comments never appear in spans or logs; the
  `card.moved` event carries ids only.
- No frontend (browser) telemetry in this iteration.

## Metric reference

| Prometheus name | Type | Labels | Meaning |
|---|---|---|---|
| `kanban_http_requests_total` | counter | `http_request_method`, `http_route`, `http_response_status_code` | requests served |
| `kanban_http_request_duration_milliseconds_{bucket,sum,count}` | histogram | same | wall time per request |
| `kanban_card_moves_total` | counter | — | cards moved between columns |
| `httpcheck_status` | gauge | `http_url`, `http_status_class`, `http_status_code` | 1 for the class the last `/health` probe returned |

Every series also carries `service_name`, `service_version` (the deployed
commit, from `/health`'s `version`) and `deployment_environment_name`.

Useful queries:

```promql
sum(rate(kanban_http_requests_total[1m]))                                             # throughput
histogram_quantile(0.95, sum by (le) (rate(kanban_http_request_duration_milliseconds_bucket[5m])))
sum(rate(kanban_http_requests_total{http_response_status_code=~"5.."}[5m]))
  / sum(rate(kanban_http_requests_total[5m]))                                         # 5xx ratio
sum(increase(kanban_card_moves_total[5m]))                                            # the journey
max(httpcheck_status{http_status_class="2xx"})                                        # 1 = API up
```

## Retention and cost

Local only: Prometheus keeps 7 days, Loki 7 days (`168h`), Tempo its default
14 days, all on named Docker volumes (`docker compose -f … down -v` wipes
them). Nothing is
sent anywhere outside the Compose network. In production the same backend
would point `OTEL_EXPORTER_OTLP_ENDPOINT` at a hosted Collector or Grafana
Cloud's OTLP endpoint; no code change is involved.

## Screenshot

![Grafana dashboard with live traffic](images/grafana-dashboard.png)

## Alerts and the responder

See [`alerting.md`](alerting.md) for the rules in `observability/alerts.yaml`
and the way to trigger one on purpose, and [`oncall.md`](oncall.md) for what
happens when one fires.
