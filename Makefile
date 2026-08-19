.PHONY: dev migrate api api-replica2 test web web-install web-test \
	topics ingest processor-install processor processor-test replay-dlq \
	benchmark-seed

dev:
	docker compose up -d
	@echo "Postgres, Redpanda, Redis on :5432/:9092/:6379."
	@echo "Run 'make migrate' and 'make topics' once healthy, then 'make api'."

migrate:
	cd services/api-service && . .venv/bin/activate && alembic upgrade head

api:
	cd services/api-service && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# A second replica of the exact same service, same Postgres/Redis/Kafka --
# the multi-replica WebSocket fan-out demo (docs/adr/0009) needs two
# independent processes to prove a message reaches both regardless of
# which one's Kafka consumer instance actually saw it.
api-replica2:
	cd services/api-service && . .venv/bin/activate && uvicorn app.main:app --port 8010

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

# --- Phase 5: TimescaleDB query optimization ---

# Seeds ~1M rows of realistic (interleaved multi-flight) synthetic
# telemetry -- see docs/BENCHMARKS.md and scripts/benchmark_seed.sql.
benchmark-seed:
	docker compose exec -T postgres psql -U telemetry -d telemetry -f - < scripts/benchmark_seed.sql
