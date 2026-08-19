# ingest-service

Stateless HTTP → Kafka bridge: validates each telemetry packet and
forwards it onto `telemetry.raw`, keyed by `vehicle_id` (see
`docs/adr/0007`), or routes it to `telemetry.dlq` if it fails
validation. Never touches Postgres — all stateful processing (dedup, DB
writes, the outbox) lives in the `processor` service.

## Setup

Requires Go 1.26+.

```
go mod download
```

## Run

```
go run .
```

Configurable via env vars (both optional):
- `KAFKA_BROKERS` — comma-separated broker list (default `localhost:9092`)
- `PORT` — HTTP port (default `8081`)

## Endpoints

- `POST /v1/ingest` — accepts a telemetry packet as JSON, returns `202`
  once it's queued (not once it's published — see `ingest.go` for the
  bounded-channel backpressure/load-shedding design)
- `GET /healthz` — liveness check
- `GET /stats` — queue depth / worker stats

## Test

```
go test ./...
go vet ./...
```
