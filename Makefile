.PHONY: help install install-frontend db-up db-down db-reset migrate revision \
	test e2e lint typecheck build-frontend format dev-backend dev-frontend clean

UV ?= uv
NPM ?= npm

help:
	@echo "make install         - uv sync (backend deps)"
	@echo "make install-frontend - npm install (frontend deps)"
	@echo "make db-up           - start Postgres via docker compose"
	@echo "make db-down         - stop Postgres"
	@echo "make db-reset        - drop + recreate Postgres volume"
	@echo "make migrate         - alembic upgrade head"
	@echo "make revision m=...  - autogenerate Alembic revision (e.g. make revision m=\"add foo\")"
	@echo "make test            - pytest"
	@echo "make e2e             - Playwright browser regression checks"
	@echo "make lint            - ruff and ESLint checks"
	@echo "make typecheck       - TypeScript validation"
	@echo "make build-frontend  - Next.js production build"
	@echo "make format          - ruff check --fix + ruff format"
	@echo "make dev-backend     - uvicorn micar.app:app --reload on :8090"
	@echo "make dev-frontend    - next dev on :3000"
	@echo "make clean           - remove caches"

install:
	cd backend && $(UV) sync

install-frontend:
	cd frontend && $(NPM) install

db-up:
	docker compose up -d --wait postgres

db-down:
	docker compose down

db-reset:
	docker compose down -v && docker compose up -d postgres

migrate:
	cd backend && $(UV) run alembic upgrade head

revision:
	cd backend && $(UV) run alembic revision --autogenerate -m "$(m)"

test:
	cd backend && $(UV) run pytest -q

e2e:
	$(MAKE) db-up
	$(MAKE) migrate
	cd frontend && $(NPM) run e2e

lint:
	cd backend && $(UV) run ruff check src tests
	cd frontend && $(NPM) run lint

typecheck:
	cd frontend && $(NPM) run typecheck

build-frontend:
	cd frontend && $(NPM) run build

format:
	cd backend && $(UV) run ruff check --fix src tests && $(UV) run ruff format src tests

dev-backend:
	cd backend && $(UV) run uvicorn micar.app:app --reload --host 0.0.0.0 --port 8090

dev-frontend:
	cd frontend && $(NPM) run dev

clean:
	rm -rf backend/.ruff_cache backend/.pytest_cache backend/.mypy_cache
	find backend -type d -name __pycache__ -prune -exec rm -rf {} +
