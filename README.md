# Mission Telemetry Platform

A distributed, multi-tenant telemetry platform for tracking rocket flights —
built incrementally, phase by phase, as a learning project. See
`docs/adr/` for the reasoning behind each architectural decision.

## Status: Phase 3 complete

Phase 1 (`services/api-service`): Postgres schema, Alembic migrations,
JWT auth with rotating refresh tokens, RBAC (owner/engineer/viewer),
CRUD for vehicles/flights.

Phase 2 (`web`): React 19 + TypeScript SPA — login/register, a
TanStack-Query-backed vehicles/flights UI, and a TypeScript API client
generated from the backend's own OpenAPI schema so the two can't
silently drift apart.

Phase 3 (`services/ingest-service`, `services/processor`): a real
event-driven ingestion pipeline on Kafka (via Redpanda — see
`docs/adr/0006`). `ingest-service` (Go) validates each telemetry packet
and forwards it to `telemetry.raw`, partitioned by `vehicle_id` for
per-vehicle ordering (`docs/adr/0007`). `processor` (Python) consumes
it, dedupes idempotently via Redis with a DB-level unique constraint as
defense-in-depth, and writes each point to Postgres alongside a
transactional outbox row (`docs/adr/0008`) that a separate relay task
publishes to `telemetry.processed`. Both services route failures to a
shared `telemetry.dlq` topic, replayable via a standalone CLI.

## Quickstart

Backend:
```
make dev      # docker compose up -d (Postgres, Redpanda, Redis)
make topics   # create telemetry.raw / .processed / .dlq
make migrate  # alembic upgrade head
make api      # uvicorn --reload on :8000
make test     # pytest
```

Frontend (needs the backend running first — it generates its types
from the live API):
```
make web-install  # npm install
make web          # vite dev server on :5173
make web-test     # vitest
```

Telemetry pipeline (needs `make dev` + `make topics` + `make migrate`
first):
```
make ingest              # go run . on :8081 (services/ingest-service)
make processor-install   # one-time: uv venv + editable installs
make processor           # consumer + outbox relay (services/processor)
make processor-test      # pytest
make replay-dlq          # replay everything currently in telemetry.dlq
```
