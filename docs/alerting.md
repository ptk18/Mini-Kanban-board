# Alerting

Two alerts, both about what users experience, neither about CPU or memory.
They live in [`observability/alerts.yaml`](../observability/alerts.yaml),
are evaluated by Prometheus every 10 s, and go through Alertmanager
([`observability/alertmanager.yml`](../observability/alertmanager.yml)) to
the on-call responder's webhook (`http://oncall:9000/alert`, see
[`oncall.md`](oncall.md)).

| Alert | Fires when | Why this threshold |
|---|---|---|
| **KanbanApiErrors** | more than **5 %** of requests to `/boards*` and `/cards*` returned 5xx over the last **1 minute**, sustained for **30 s** | A ratio, not a count: one flaky request on a quiet board must not page anyone, while one failure in twenty, kept up for half a minute, means people cannot work on their boards. The window is short because the product is interactive; a user notices within seconds. |
| **KanbanApiDown** | the last successful `/health` probe sample is more than **60 s** old, sustained for **30 s** | The probe runs every 10 s; six misses in a row is an outage, not a blip. Deploys restart the container in well under a minute, so a normal release does not fire it. |

Both are `severity: critical` and carry a `summary`, a `description` and a
`runbook` link back to this page.

## KanbanApiErrors

```promql
(
  sum(rate(kanban_http_requests_total{http_route=~"/boards.*|/cards.*", http_response_status_code=~"5.."}[1m]))
  /
  sum(rate(kanban_http_requests_total{http_route=~"/boards.*|/cards.*"}[1m]))
) > 0.05
```

What to look at: the `level=error` `http.request` log lines in Loki (they
carry `error.type` and `error.message`), the failing route's traces in
Tempo, and the "Responses by status class" panel. The responder collects
exactly this (see `oncall/collect-evidence.sh`).

## KanbanApiDown

```promql
(time() - max(timestamp(httpcheck_status{http_status_class="2xx", http_status_code="200", http_url=~".*/health"})) > 60)
or absent(httpcheck_status{http_status_class="2xx", http_status_code="200", http_url=~".*/health"})
```

Why the rule asks for the *age of the last good sample* instead of a value:
when the probe fails, the Collector emits a *different* `httpcheck_status`
series (no `http_status_code` label) at 0, the healthy `…code="200"` series
simply stops, and Prometheus keeps answering with its last value for the
five-minute lookback. Comparing values therefore stays "up" for minutes;
`timestamp()` reports when that last sample really arrived and grows the
moment the backend stops. `collector.yaml` sets `metric_expiration: 30s`
so stale series leave the exporter quickly; the app's own counters are
re-exported every 10 s and are not affected.

What to look at: `docker compose ps backend`, the backend's last log lines
(a startup failure prints a traceback; a missing `JWT_SECRET` or an
unreachable database are the usual causes), and whether the database is
healthy.

## Triggering an alert on purpose

The local stack runs the backend with `FAULT_INJECTION=1`
(`observability/compose.yaml`), which registers one extra route,
`POST /debug/fault`. Switched on, every **card move** (a `PATCH` that changes
the column) raises inside the handler and answers `500`; reads, edits and
reorders keep working, so the alert sees a realistic partial outage. The
route and the failure path do not exist unless the variable is set, and
`render.yaml` never sets it.

```sh
make observe          # the stack
make seed             # the demo board (once)
make demo-alert       # inject → drive traffic → wait for FIRING → clear the fault
```

`observability/demo-alert.sh` prints one line per second with the move
responses (`500 500 500`) and the alert state (`inactive → pending →
firing`), then shows what Alertmanager received. It takes about a minute:
up to 60 s for the 1-minute rate window to fill plus the 30 s `for`. Pass
`--keep` to leave the fault on for the on-call demo; clear it by hand with

```sh
curl -X POST localhost:8000/debug/fault -H 'Content-Type: application/json' -d '{"card_move_fails": false}'
```

To see **KanbanApiDown** instead: `docker compose stop backend`, wait a little
over a minute, `docker compose start backend`. The alert resolves on its own
once the probe sees 2xx again.

## Where to see alerts

- Prometheus: http://localhost:9090/alerts (rule state: inactive / pending / firing)
- Alertmanager: http://localhost:9093 (what was delivered, and to whom)
- Grafana: the dashboard's 5xx-ratio stat turns orange above 1 % and red above 5 %

## What is deliberately not alerted on

Latency (p95 is tens of milliseconds locally and the product tolerates a
slow second), 4xx rates (a wrong password is a 401, not an incident),
and anything about hosts or containers. If a resource problem matters it
shows up as one of the two alerts above, which is the only way it matters
to a user.
