# Backlog, part 2: from MVP to production

Continues `tasks.md` (issues #1–#38, the MVP). These are issues #39–#47 on
GitHub, one per task, each with acceptance criteria in the issue body and a
closing comment that lists what shipped and the verification that was run.

## 39. Migrate the database to Postgres with Alembic migrations
Goal: Postgres in Docker and production, Alembic migrations instead of `create_all`; SQLite stays for the unit suite.

## 40. Containerize the full stack with Docker Compose
Goal: `docker compose up` from a clean checkout starts Postgres, the backend (migrated) and the frontend.

## 41. Add integration tests against Postgres and a Playwright end-to-end test
Goal: migrations, the main journey and the seed proven against real Postgres; the browser flow proven against the Compose stack; one command runs every layer.

## 42. Add GitHub Actions CI that runs lint, tests and the container build on every pull request
Goal: every PR and push to main runs unit, integration, image builds and e2e; a red check blocks merging.

## 43. Add the Render deployment blueprint, CD workflow and release/rollback docs
Goal: deploy-ready for Render; dev deploys automatically after green CI, production is manual and approval-gated; rollback documented.

## 44. Instrument the backend with OpenTelemetry and run a local Grafana observability stack
Goal: the card-move journey emits traces, metrics and structured logs that share a trace id, collected into Tempo, Prometheus and Loki and shown in Grafana.

## 45. Add an alert on user-facing errors and a deliberate way to trigger it
Goal: 5xx ratio and availability alerts on user impact, routed to Alertmanager; a demo fault switch to fire them on purpose.

## 46. Build the on-call responder agent triggered by the alert
Goal: an alert wakes headless Claude Code with bounded evidence, a worktree, a policy and a schema; it diagnoses, acts within policy and verifies recovery.

## 47. Expand AGENTS.md, add the AI-tools write-up, screenshots and a rubric map to the README
Goal: a reviewer finds everything from the README; an agent starting a session is pointed at every document.
