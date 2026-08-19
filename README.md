# Mission Telemetry Platform

A distributed, multi-tenant telemetry platform for tracking rocket flights —
built incrementally, phase by phase, as a learning project. See
`docs/adr/` for the reasoning behind each architectural decision.

## Status: Phase 2 complete

Phase 1 (`services/api-service`): Postgres schema, Alembic migrations,
JWT auth with rotating refresh tokens, RBAC (owner/engineer/viewer),
CRUD for vehicles/flights.

Phase 2 (`web`): React 19 + TypeScript SPA — login/register, a
TanStack-Query-backed vehicles/flights UI, and a TypeScript API client
generated from the backend's own OpenAPI schema so the two can't
silently drift apart.

## Quickstart

Backend:
```
make dev      # docker compose up -d (Postgres)
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
