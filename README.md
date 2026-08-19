# Mission Telemetry Platform

A distributed, multi-tenant telemetry platform for tracking rocket flights —
built incrementally, phase by phase, as a learning project. See
`docs/adr/` for the reasoning behind each architectural decision.

## Status: Phase 5 complete

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

Phase 4 (`services/api-service/app/ws`): live telemetry over WebSocket
(`GET /ws/flights/{id}`), fanned out correctly across multiple
api-service replicas via Redis pub/sub (`docs/adr/0009`) — Kafka's
consumer group hands `telemetry.processed` to exactly one replica,
which republishes to Redis so every replica's browsers get it,
regardless of which one did the consuming. Each connection has a
bounded outbound queue that drops (not buffers) under backpressure. The
web client (`web/src/ws`) reconnects on drop with full-jitter
exponential backoff, visible live on the flight detail page.

Phase 5 (`telemetry_points` as a TimescaleDB hypertable): `telemetry_points`
is now partitioned on `ts` in 1-day chunks (`docs/adr/0010`), with a
`telemetry_1m` continuous aggregate backing fast per-flight summaries.
`GET /v1/flights/{id}/telemetry` is keyset-paginated (`docs/adr/0011`)
rather than `OFFSET`/`LIMIT` — safe under the concurrent writes this
table is never not under — and `GET /v1/flights/{id}/telemetry/summary`
reads the continuous aggregate directly. Both are wired into the flight
detail page. `docs/BENCHMARKS.md` has the real, measured before/after:
the composite index cuts buffer reads ~42x on paginated queries, and the
continuous aggregate is ~224x faster than computing the same summary
live over 500k raw points.

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

WebSocket fan-out demo (needs the telemetry pipeline above running too
— it's what actually produces `telemetry.processed` events to fan out):
```
make api           # replica 1, :8000 (same command as above)
make api-replica2  # replica 2, :8010 -- same Postgres/Redis/Kafka
```
Open a flight's detail page in the web app (or connect two WebSocket
clients, one per port, to `/ws/flights/{id}?token=<access_token>`) and
send a packet through `make ingest` — both replicas' connections
receive the identical update. `GET /v1/ws/stats` on either port shows
that replica's local connection count and backpressure drop count.

Query-optimization benchmarks (needs `make dev` + `make migrate`):
```
make benchmark-seed   # ~1M rows of realistic synthetic telemetry, ~10-15s
```
See `docs/BENCHMARKS.md` for the real `EXPLAIN ANALYZE` output this
data produces and how to reproduce it yourself.
