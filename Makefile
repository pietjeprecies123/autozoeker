.PHONY: install dev backend frontend build test lint typecheck seed crawl retrain verify-sources capture docker up down

install:
	cd backend && uv sync
	cd frontend && npm ci

dev: ## run backend (8000) and frontend dev server (5173) together
	@echo "Backend http://localhost:8000  ·  Frontend http://localhost:5173"
	(cd backend && uv run uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev) ; wait

backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

test:
	cd backend && uv run pytest
	cd frontend && npm test

lint:
	cd backend && uv run ruff check app tests

typecheck:
	cd frontend && npm run typecheck

seed:
	cd backend && uv run python -m app.cli seed-demo

crawl:
	cd backend && uv run python -m app.cli crawl

retrain:
	cd backend && uv run python -m app.cli retrain

verify-sources:
	cd backend && uv run python -m app.cli verify-sources

capture:
	cd backend && uv run python -m app.cli capture autoscout24 && uv run python -m app.cli capture marktplaats

docker:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down
