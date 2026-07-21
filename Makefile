.PHONY: help install up down api worker beat migrate revision fmt lint type test test-unit test-int check demo clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Sync deps and create .env from the example
	uv sync
	@test -f .env || (cp .env.example .env && echo "created .env from .env.example")

up:  ## Start Postgres(+pgvector) and Redis
	docker compose up -d db redis
	@echo "waiting for healthchecks..."
	@timeout 60 sh -c 'until [ "$$(docker inspect -f "{{.State.Health.Status}}" $$(docker compose ps -q db))" = "healthy" ]; do sleep 1; done'
	@echo "db ready"

down:  ## Stop the local stack
	docker compose down

api:  ## Run the API (http://localhost:8000/docs)
	uv run uvicorn app.main:app --reload

worker:  ## Run a Celery worker on both queues
	uv run celery -A app.workers.celery_app worker -Q io,cpu -l info

beat:  ## Run the Celery scheduler
	uv run celery -A app.workers.celery_app beat -l info

migrate:  ## Apply migrations
	uv run alembic upgrade head

revision:  ## Autogenerate a migration: make revision m="add x"
	uv run alembic revision --autogenerate -m "$(m)"

fmt:  ## Format
	uv run ruff format app tests
	uv run ruff check --fix app tests

lint:  ## Lint (no fixes)
	uv run ruff format --check app tests
	uv run ruff check app tests

type:  ## Type-check
	uv run mypy app

test-unit:  ## Pure-logic tests
	uv run pytest tests -m "not integration"

test-int:  ## DB-backed tests (testcontainers; needs Docker)
	uv run pytest tests -m integration

test: test-unit  ## Alias for the fast suite

check: lint type test-unit  ## What CI runs

demo:  ## Week 3 spike: print real matches + "why this fits you" explanations
	@echo "not built yet — Week 3. See the plan."

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
