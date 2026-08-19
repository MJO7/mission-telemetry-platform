# processor

Consumes `telemetry.raw`, dedupes via Redis, writes each new point to
Postgres plus an outbox row (see `app/models/outbox.py` in api-service),
and relays outbox rows to `telemetry.processed`. See `docs/adr/0006`
through `0008` for the design decisions.

Deliberately reuses api-service's SQLAlchemy models and `Settings`
(`app.models.telemetry`, `app.models.outbox`, `app.core.config`,
`app.core.db`) instead of a second, independently-maintained copy of the
same tables -- that would be exactly the frontend/backend drift risk
ADR-0005 already named, just between two Python services instead of a
frontend and a backend.

## Setup

```
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
uv pip install -e ../api-service   # for the shared app.* package
```

(Plain `python3.12 -m venv .venv` + `pip install` works too -- `uv` is
just faster. `make processor-install` runs the above from the repo root.)

## Run

```
python -m processor.main
```

## Replay the dead-letter queue

```
python -m processor.replay_dlq            # replay everything currently in telemetry.dlq
python -m processor.replay_dlq --max 10    # replay at most 10 messages
```
