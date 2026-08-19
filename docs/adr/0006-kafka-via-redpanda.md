# ADR-0006: Kafka (via Redpanda) as the telemetry event backbone

**Status:** Accepted — Phase 3

## Context
Telemetry ingestion needs to decouple "a packet arrived" from "a packet
is processed": ingest-service must accept packets fast and keep
accepting them even if the processor, database, or downstream consumers
are slow or momentarily down. That decoupling needs a durable,
ordered, replayable log between the two — not a direct HTTP call or an
in-memory queue that dies with the process.

## Decision
Use the Kafka wire protocol as the event backbone, with **Redpanda**
(not Apache Kafka + ZooKeeper) as the concrete broker for local dev and
this project's scope:
- Single binary, no JVM, no separate ZooKeeper/KRaft cluster to run —
  `docker compose up` gets one broker healthy in seconds.
- Wire-protocol compatible with real Kafka, so the client libraries
  (`segmentio/kafka-go` in Go, `aiokafka` in Python) and every
  partitioning/consumer-group concept transfer directly to a real Kafka
  or MSK deployment later without code changes.
- Three topics: `telemetry.raw` (ingest → processor), `telemetry.dlq`
  (both services' failure sink), `telemetry.processed` (processor →
  future consumers, via the outbox relay — see ADR-0008).

## Alternatives considered
**Redis Streams / a Postgres-backed queue.** Rejected: this project's
build spec explicitly targets Kafka-shaped skills (partitioning,
consumer groups, at-least-once delivery, replay) as the signal worth
demonstrating — a queue that doesn't have those concepts doesn't
exercise them.

**Running real Apache Kafka + ZooKeeper in Docker Compose.** Rejected
for local dev: meaningfully heavier (JVM, multiple containers,
slower cold start) for zero behavioral difference at this scale: the
wire protocol, not the broker implementation, is what the rest of the
system is written against.

## Consequences
Local dev and this codebase are broker-agnostic by construction — that
portability is the point, not an accident. Redpanda-specific operational
knowledge (e.g. `rpk` tooling) doesn't transfer to a real Kafka ops team
1:1, but that gap is in tooling, not in the architecture being
demonstrated.
