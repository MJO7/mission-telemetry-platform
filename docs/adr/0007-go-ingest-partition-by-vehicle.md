# ADR-0007: Go for ingest-service, partitioned by vehicle_id

**Status:** Accepted — Phase 3

## Context
Ingest-service is the system's single highest-throughput, most
latency-sensitive path: every telemetry packet from every vehicle
passes through it before anything else sees it. Two separate decisions
had to be made here: which language to write it in, and how to
partition the Kafka topic it produces to.

## Decision

**Go**, not Python, for ingest-service. Reasons specific to this
service's job, not a blanket "Go is better" claim:
- Goroutines + a bounded channel give cheap, native backpressure
  (`select` with a `default` case load-sheds instead of blocking) at a
  concurrency level that would need real engineering effort to match in
  Python's asyncio for a comparably simple amount of code.
- A single static binary with no interpreter/runtime dependency matches
  what this service actually is: a thin, stateless validate-and-forward
  layer that never touches Postgres — all the stateful, business-logic
  work (dedup, DB writes, the outbox) lives in the processor service,
  which stays in Python specifically because that logic benefits more
  from Python's ecosystem (SQLAlchemy, the shared `app` models) than
  from Go's concurrency primitives.

**Partition `telemetry.raw` by `vehicle_id`** (used as the Kafka message
key), not randomly and not by `flight_id`:
- Every message for a given vehicle lands in the same partition, and
  Kafka only guarantees ordering *within* a partition — so this is what
  guarantees a processor consumer never sees vehicle A's packets out of
  order, even though the topic has multiple partitions and (eventually)
  multiple consumer instances.
- `flight_id` was considered and rejected: a vehicle's flights are
  sequential in time but not necessarily co-located usefully across
  partitions, and per-vehicle ordering is the guarantee that actually
  matters (a vehicle's own telemetry stream must be strictly ordered;
  cross-vehicle ordering was never a requirement).

## Alternatives considered
**Python (FastAPI) for ingest-service too**, matching the rest of the
backend. Rejected for this specific service on the throughput/backpressure
reasoning above — and rejected as "just use Python everywhere" on
purpose, since a polyglot system with a clear, principled reason for
each language choice is itself part of what this project is meant to
demonstrate.

**No explicit partition key (random/round-robin).** Rejected: it would
maximize throughput evenness across partitions but destroy the one
ordering guarantee a telemetry pipeline actually needs.

## Consequences
Partition count is a hard ceiling on consumer parallelism for a single
consumer group (3 partitions today → at most 3 processor instances
usefully consuming `telemetry.raw` at once); repartitioning later means
a topic migration, not a config flag. A vehicle with unusually high
packet volume also can't be split across partitions — its whole stream
is one partition's problem, which is the accepted tradeoff for strict
per-vehicle ordering.
