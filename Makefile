.PHONY: dev migrate api test

dev:
	docker compose up -d
	@echo "Postgres on :5432. Run 'make migrate' once it's healthy, then 'make api'."

migrate:
	cd services/api-service && . .venv/bin/activate && alembic upgrade head

api:
	cd services/api-service && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

test:
	cd services/api-service && . .venv/bin/activate && pytest -q
