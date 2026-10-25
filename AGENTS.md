Commands

- `uv sync` - install dependencies
- `uv run pytest` - the whole suite
- `uv run pytest tests/test_home.py` - one test file
- `make test` - every layer (unit, Postgres integration, browser e2e); `make test-unit` is the Docker-free subset
- `make up` / `make observe` - the stack (and the observability stack) in Docker; `make help` lists everything

Rules

- Dependencies are added in `pyproject.toml`. Do not add one without
  asking
- Work is tracked as GitHub issues, one per task, each with acceptance
  criteria; read them before starting and before closing (`_docs/process.md`)
- Never put e-mails, tokens, titles or request bodies in logs, spans or
  metrics (`docs/observability.md`); `FAULT_INJECTION` and `/debug/fault`
  are local-demo only and must never reach `render.yaml`

Where things are documented

- `README.md` - what the product does, how to run it, the rubric map
- `_docs/plan.md` - the product specification (MVP scope, data model, API)
- `_docs/tasks.md`, `_docs/tasks-production.md` - the backlog (MVP, then production); issues #1-#47 on GitHub are the tracker
- `_docs/process.md` - how a task moves from issue to closed, and who does what
- `_docs/team/pm.md`, `_docs/team/software-engineer.md`, `_docs/team/qa-engineer.md` - the agent roles
- `_docs/task-template.md` - the shape of an issue
- `_docs/design-system.md` - visual direction and tokens
- `_docs/testing-guidelines.md` - how to write tests; `docs/testing.md` - how to run them and what each layer proves
- `backend/README.md`, `frontend/README.md` - per-app commands and API reference
- `docs/deployment.md`, `docs/release-process.md` - Render, CI/CD, promotion, rollback
- `docs/observability.md`, `docs/alerting.md`, `docs/oncall.md`, `docs/oncall-demo.md` - telemetry, alerts, the responder
- `frontend/AGENTS.md` - Next.js version notes that override training data
