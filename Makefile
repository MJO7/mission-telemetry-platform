.PHONY: dev migrate api test web web-install web-test

dev:
	docker compose up -d
	@echo "Postgres on :5432. Run 'make migrate' once it's healthy, then 'make api'."

migrate:
	cd services/api-service && . .venv/bin/activate && alembic upgrade head

api:
	cd services/api-service && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

test:
	cd services/api-service && . .venv/bin/activate && pytest -q

web-install:
	cd web && npm install

web:
	cd web && npm run dev

web-test:
	cd web && npm test
