# Entry points for the whole system. `make help` lists them.
#
# Compose targets use docker-compose.yml at the repo root; the dev targets run
# the apps directly (two terminals, SQLite) as described in README.md.

COMPOSE ?= docker compose

.DEFAULT_GOAL := help

.PHONY: help up down logs ps seed test test-unit test-backend test-frontend test-integration test-e2e dev-backend dev-frontend

help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Build and start Postgres, backend and frontend (http://localhost:3000)
	$(COMPOSE) up --build -d
	@echo "Frontend http://localhost:3000   Backend http://localhost:8000/docs"

down: ## Stop the stack (data is kept; `docker compose down -v` wipes it)
	$(COMPOSE) down

logs: ## Follow the logs of every service
	$(COMPOSE) logs -f

ps: ## Show service status and health
	$(COMPOSE) ps

seed: ## Load the demo board into the running stack
	$(COMPOSE) exec backend python scripts/seed.py

# Host port of the Compose database (docker-compose.yml default). Override with POSTGRES_PORT=....
POSTGRES_PORT ?= 5433
TEST_DATABASE_URL ?= postgresql+psycopg://kanban:kanban@127.0.0.1:$(POSTGRES_PORT)/kanban

test: test-unit test-integration test-e2e ## Every layer: unit, Postgres integration, browser e2e

test-unit: test-backend test-frontend ## Fast suites only, no Docker: backend pytest on SQLite, frontend vitest

test-integration: ## Backend against a real Postgres (starts the Compose db if needed)
	$(COMPOSE) up -d db --wait
	cd backend && TEST_DATABASE_URL=$(TEST_DATABASE_URL) uv run pytest tests/integration

test-e2e: ## Playwright against the full Compose stack (built, started, then stopped)
	$(COMPOSE) up -d --build --wait
	cd frontend && npx playwright test; status=$$?; cd .. && $(COMPOSE) down; exit $$status

test-backend: ## Backend unit tests
	cd backend && uv run pytest

test-frontend: ## Frontend unit tests
	cd frontend && npm test

dev-backend: ## Run the backend on SQLite with reload (needs JWT_SECRET in the shell)
	cd backend && uv run uvicorn app.main:app --reload

dev-frontend: ## Run the Next.js dev server
	cd frontend && npm run dev
