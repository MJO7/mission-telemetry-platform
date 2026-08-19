# Mission Telemetry Platform

A distributed, multi-tenant telemetry platform for tracking rocket flights —
built incrementally, phase by phase, as a learning project. See
`docs/adr/` for the reasoning behind each architectural decision.

## Status: Phase 1 in progress

## Quickstart
```
make dev      # docker compose up -d (Postgres)
make migrate  # alembic upgrade head
make api      # uvicorn --reload on :8000
make test     # pytest
```