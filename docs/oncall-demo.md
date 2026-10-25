# On-call demo — recorded run

A verbatim run of `make demo-oncall` on the local stack (20261025T150216Z UTC), lightly
trimmed: the one-per-second traffic lines are collapsed and the SQL text in
the trace is elided. Nothing else is edited. Design: [`oncall.md`](oncall.md).

**Verdict:** `RECOVERED — KanbanApiErrors (20261025T150216Z)`

## 1. The incident is created and the alert fires

```text
oncall/demo.sh
alertmanager recreated (fresh notification log)
receiver up on :9000 (pid 70117)
22:01:15 logging in as the seeded owner (run 'make seed' first if this fails)
22:01:16 switching the fault on: card moves will answer 500
{"card_move_fails":true}
22:01:16 driving traffic: a card move every second (each one fails), plus healthy reads
500/200 500/200 500/200 | KanbanApiErrors: …  (43 more lines like this, one per second: each card is moved to the last column, which fails, then to the first, which is a no-op)
500/200 500/200 500/200 | KanbanApiErrors: firing
22:02:07 ALERT FIRING after 44 rounds
   KanbanApiErrors firing | Board/card requests are failing (42.5% 5xx over 1m)
22:02:22 Alertmanager received:
   KanbanApiErrors active receivers: ['oncall']
22:02:22 fault LEFT ON (--keep); clear it with: curl -X POST http://localhost:8000/debug/fault -H 'Content-Type: application/json' -d '{"card_move_fails": false}'
```

## 2. Alertmanager calls the receiver, the responder runs

The receiver's log (`oncall/reports/server.log`):

```text
22:01:14 on-call webhook listening on :9000 (POST /alert); cooldown 600s per alert
22:02:16 starting responder for KanbanApiErrors (1792940536-KanbanApiErrors.json)
22:03:16 resolved: KanbanApiErrors
22:03:23 responder for KanbanApiErrors finished with exit 0
22:03:23   22:03:23 KanbanApiErrors state=inactive condition_cleared=yes
22:03:23   RECOVERED: alert inactive, condition cleared, smoke test passed, journey: card 13 moved 1 -> 5 -> 1: 200 200
22:03:23   15:03:23 report: /Users/freya/personal/Mini-Kanban-board/oncall/reports/20261025T150216Z-KanbanApiErrors.md
receiver stopped
```

The responder's own log:

```text
15:02:17 responder start: KanbanApiErrors (turns<=30, budget<=$3)
evidence packet: /Users/freya/personal/Mini-Kanban-board/oncall/reports/20261025T150216Z-KanbanApiErrors.evidence.md (15608 bytes)
15:02:17 worktree: /Users/freya/personal/Mini-Kanban-board/oncall/worktrees/20261025T150216Z-KanbanApiErrors (oncall/20261025T150216Z-KanbanApiErrors)
15:02:43 claude exit 0
15:02:43 proposed: clear_demo_fault (confidence 0.97)
15:02:43 action: clearing the demo fault via POST /debug/fault
{"card_move_fails":false}22:02:43 KanbanApiErrors state=firing condition_cleared=no
22:02:53 KanbanApiErrors state=firing condition_cleared=no
22:03:03 KanbanApiErrors state=firing condition_cleared=yes
22:03:13 KanbanApiErrors state=firing condition_cleared=yes
22:03:23 KanbanApiErrors state=inactive condition_cleared=yes
RECOVERED: alert inactive, condition cleared, smoke test passed, journey: card 13 moved 1 -> 5 -> 1: 200 200
```

## 3. What the model answered (validated against `response.schema.json`)

```json
{
  "diagnosis": "Users' card moves (PATCH /cards/{card_id}) are returning 500 since 2026-10-25T15:01:56Z, pushing the 5xx ratio on /boards*|/cards* to ~42.9% and firing KanbanApiErrors. All 25 error log lines carry error.type=InjectedFault with the message \"fault injection: card moves are set to fail (POST /debug/fault)\", so this is the demo fault switch being on, not a real defect \u2014 the backend is otherwise healthy (health probe 2xx, p95 ~21 ms, DB queries in the failing trace succeed).",
  "root_cause": "The runtime fault-injection flag (FaultState.card_move_fails, toggled via POST /debug/fault in backend/app/routers/debug.py) is set, so check_card_move() at backend/app/fault.py:30-32 raises InjectedFault on every card move; it is invoked from backend/app/routers/cards.py:136.",
  "proposed_action": "clear_demo_fault",
  "confidence": 0.97,
  "needs_human": false,
  "verification": "PATCH /cards/{card_id} returns 200 again and no new level=error, error.type=InjectedFault log lines appear; the Prometheus 5xx ratio on /boards*|/cards* drops below 5% over 1m and the KanbanApiErrors alert resolves.",
  "fix_summary": "",
  "_cost_usd": 0.37501699999999993,
  "_turns": 4
}
```

The policy (`autonomy-policy.yaml`) marks `clear_demo_fault` automatic above
confidence 0.8 and requires the evidence to contain `InjectedFault`; both
held, so the responder cleared the switch and then ran
`verify-recovery.sh`, which waited for the alert to go inactive, the 5xx
ratio to drop, the smoke test to pass and a real card move (to another
column and back) to answer `200 200`.

## 4. The evidence packet the model reasoned from

Collected by `collect-evidence.sh` (read-only, allowlisted queries; no
environment variables, headers, bodies or e-mails):

```text
# Evidence packet: KanbanApiErrors
collected: 2026-10-25T15:02:17Z by oncall/collect-evidence.sh (read-only, allowlisted)

## Alert (from Alertmanager)
- KanbanApiErrors firing | since 2026-10-25T15:01:56.988Z
   summary: Board/card requests are failing (42.5% 5xx over 1m)
   description: More than 5% of /boards* and /cards* requests returned 5xx for 30 s. Users cannot work on their boards. Check the error log lines (level=error, event=http.request) and the traces for the failing route.
   runbook: docs/alerting.md#kanbanapierrors

## Prometheus (now)
- alerts:
   {'alertname': 'KanbanApiErrors', 'alertstate': 'firing'} => 1
- 5xx ratio on /boards*|/cards* over 1m:
   {} => 0.42857142857142855
- request rate by route and status (1m):
   {'http_request_method': 'GET', 'http_response_status_code': '200', 'http_route': '/boards/{board_id}/dashboard'} => 0.82006560524842
   {'http_request_method': 'PATCH', 'http_response_status_code': '200', 'http_route': '/cards/{card_id}'} => 2.46019681574526
   {'http_request_method': 'PATCH', 'http_response_status_code': '500', 'http_route': '/cards/{card_id}'} => 2.46019681574526
- p95 latency ms (5m):
   {} => 21.30859375
- /health probe status:
   {'http_status_class': '2xx'} => 1
- seconds since last successful /health probe:
   {} => 6.927999973297119
- card moves in the last 5m:
   (no data)

## Loki: last error log lines (level=error, newest first, max 25)
   {"duration_ms": 10.8, "http.request.method": "PATCH", "http.route": "/cards/{card_id}", "http.response.status_code": 500, "error.type": "InjectedFault", "error.message": "fault injection: card moves are set to fail (POST /debug/fault)", "event": "http.reque …
   {"duration_ms": 11.6, "http.request.method": "PATCH", "http.route": "/cards/{card_id}", "http.response.status_code": 500, "error.type": "InjectedFault", "error.message": "fault injection: card moves are set to fail (POST /debug/fault)", "event": "http.reque …
   {"duration_ms": 11.9, "http.request.method": "PATCH", "http.route": "/cards/{card_id}", "http.response.status_code": 500, "error.type": "InjectedFault", "error.message": "fault injection: card moves are set to fail (POST /debug/fault)", "event": "http.reque …
   {"duration_ms": 3.7, "http.request.method": "PATCH", "http.route": "/cards/{card_id}", "http.response.status_code": 500, "error.type": "InjectedFault", "error.message": "fault injection: card moves are set to fail (POST /debug/fault)", "event": "http.reques …
   … (21 more identical InjectedFault lines)

## Tempo: one failing trace (first error log line's trace_id)
trace_id: 1f9d54408c66d49b227d6a8b8e80b8b8
   PATCH /cards/{card_id} http receive          0.0 ms status= {}
   PATCH /cards/{card_id} http send             0.0 ms status=STATUS_CODE_ERROR {}
   PATCH /cards/{card_id} http send             0.0 ms status= {}
   PATCH /cards/{card_id}                       7.4 ms status=STATUS_CODE_ERROR {'http.route': '/cards/{card_id}'}
   connect                                      0.3 ms status= {}
   SELECT kanban                                0.3 ms status= {db.statement: …}
   SELECT kanban                                0.2 ms status= {db.statement: …}
   SELECT kanban                                0.1 ms status= {db.statement: …}
   SELECT kanban                                0.2 ms status= {db.statement: …}
   SELECT kanban                                0.1 ms status= {db.statement: …}

## Containers
alertmanager Up About a minute
backend Up 24 minutes (healthy)
db Up 2 hours (healthy)
frontend Up 24 minutes (healthy)
grafana Up 24 minutes
loki Up 24 minutes
otel-collector Up 24 minutes
prometheus Up 24 minutes
tempo Up 24 minutes

## Repository
- HEAD: 116d865 feat: alert on user impact and add a demo fault switch (66 minutes ago)
- recent commits:
   116d865 feat: alert on user impact and add a demo fault switch
   283aea0 feat(backend): instrument with OpenTelemetry and add the local Grafana stack
   7e9f1fb feat: add the Render blueprint, dev/prod deploy workflow and release docs
   369bad1 ci: pin setup-uv to v10.3.2, the action has no floating v10 tag
   536d217 ci: run lint, tests, image builds and e2e on every PR and push to main
   f4b185b test: add Postgres integration tests and Playwright end-to-end tests
   4c382c5 feat: containerize the full stack with Docker Compose
   260383b feat(backend): add Postgres support with Alembic migrations
- uncommitted changes:
    M .gitignore
    M AGENTS.md
    M Makefile
    M README.md
    M _docs/plan.md
    M _docs/tasks.md
    M docs/alerting.md
    M observability/alertmanager.yml
    M observability/alerts.yaml
    M observability/compose.yaml
    M observability/demo-alert.sh
   ?? _docs/tasks-production.md
   ?? docs/images/board.png
   ?? docs/images/boards.png
   ?? docs/images/card-modal.png
   ?? docs/images/dashboard.png
   ?? docs/images/login.png
   ?? docs/oncall.md
   ?? frontend/e2e/screenshots.mjs
   ?? oncall/
- where card moves fail on purpose, if the fault switch is on: backend/app/fault.py, backend/app/routers/debug.py, check_card_move() in backend/app/routers/cards.py
```
