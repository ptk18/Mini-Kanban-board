# Entry points for the whole system. `make help` lists them.
#
# Compose targets use docker-compose.yml at the repo root; the dev targets run
# the apps directly (two terminals, SQLite) as described in README.md.

COMPOSE ?= docker compose

.DEFAULT_GOAL := help

.PHONY: help up down logs ps seed test test-unit test-backend test-frontend dev-backend dev-frontend

help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

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

test: test-unit ## Run every test suite (unit now; integration and e2e are added by #41)

test-unit: test-backend test-frontend ## Fast suites only: backend pytest on SQLite, frontend vitest

test-backend: ## Backend unit tests
	cd backend && uv run pytest

test-frontend: ## Frontend unit tests
	cd frontend && npm test

dev-backend: ## Run the backend on SQLite with reload (needs JWT_SECRET in the shell)
	cd backend && uv run uvicorn app.main:app --reload

dev-frontend: ## Run the Next.js dev server
	cd frontend && npm run dev
