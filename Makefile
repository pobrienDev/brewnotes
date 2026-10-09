.PHONY: db db-down install migrate migration seed dev dev-backend dev-frontend dev-fake-login test test-backend test-frontend e2e lint lint-backend lint-frontend types check openapi

BACKEND := cd backend && uv run
FRONTEND := cd frontend && npm

## Database
db:            ## Start Postgres 18 in Docker
	docker compose up -d --wait postgres

db-down:       ## Stop Postgres (data is kept in the named volume)
	docker compose down

## Dependencies
install:
	cd backend && uv sync --all-groups
	cd frontend && npm ci

## Migrations
migrate:
	$(BACKEND) alembic upgrade head

migration:     ## make migration m="describe change"
	$(BACKEND) alembic revision --autogenerate -m "$(m)"

seed:
	$(BACKEND) python -m app.cli seed

## Development servers
dev:
	@$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	$(BACKEND) uvicorn app.main:app --reload --port 8000

dev-frontend:
	$(FRONTEND) run dev

dev-fake-login: ## Backend with a fake GitHub sign-in (no OAuth app needed); pairs with dev-frontend
	$(BACKEND) uvicorn tests.e2e.harness:app --reload --port 8000

## Tests
test: test-backend test-frontend

test-backend:
	$(BACKEND) pytest

test-frontend:
	$(FRONTEND) test -- --run

e2e:           ## Browser smoke tests; needs dev-fake-login and dev-frontend running (E2E_BASE_URL overrides)
	$(FRONTEND) exec playwright test

## Lint and type checks
lint: lint-backend lint-frontend

lint-backend:
	$(BACKEND) ruff check .
	$(BACKEND) ruff format --check .
	$(BACKEND) mypy .

lint-frontend:
	$(FRONTEND) run lint
	$(FRONTEND) run typecheck

## OpenAPI contract
openapi:
	$(BACKEND) python -m app.cli export-openapi --out ../frontend/openapi.json

types: openapi   ## Regenerate frontend API types from the backend spec
	$(FRONTEND) run generate-api

## Everything CI runs
check: lint test
	$(BACKEND) alembic check
	$(MAKE) types
	git diff --exit-code -- frontend/openapi.json frontend/src/api/schema.d.ts
