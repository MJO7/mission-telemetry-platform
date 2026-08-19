.PHONY: dev migrate api test web web-install web-test \
	topics ingest processor-install processor processor-test replay-dlq

dev:
	docker compose up -d
	@echo "Postgres, Redpanda, Redis on :5432/:9092/:6379."
	@echo "Run 'make migrate' and 'make topics' once healthy, then 'make api'."

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

# --- Phase 3: Kafka/Redpanda pipeline ---

topics:
	docker compose exec redpanda rpk topic create telemetry.raw --partitions 3 || true
	docker compose exec redpanda rpk topic create telemetry.processed --partitions 3 || true
	docker compose exec redpanda rpk topic create telemetry.dlq --partitions 1 || true

ingest:
	cd services/ingest-service && go run .

processor-install:
	cd services/processor && uv venv --python 3.12 .venv \
		&& . .venv/bin/activate && uv pip install -e ".[dev]" && uv pip install -e ../api-service

processor:
	cd services/processor && . .venv/bin/activate && python -m processor.main

processor-test:
	cd services/processor && . .venv/bin/activate && pytest -q

replay-dlq:
	cd services/processor && . .venv/bin/activate && python -m processor.replay_dlq
