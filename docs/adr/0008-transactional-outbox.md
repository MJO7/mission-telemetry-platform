# ADR-0008: Transactional outbox for Postgres → Kafka publication

**Status:** Accepted — Phase 3

## Context
The processor writes a `TelemetryPoint` to Postgres *and* needs to
publish a corresponding event to `telemetry.processed` for downstream
consumers. Postgres and Kafka are two separate systems with no shared
transaction — there is no way to atomically "commit to Postgres and
publish to Kafka" as one operation. Whichever order those two writes
happen in, a crash between them creates a real inconsistency:
- **DB write, then Kafka publish:** crash after the DB commit but before
  the publish → the point exists in Postgres but downstream consumers
  never hear about it. Silent data loss from their point of view.
- **Kafka publish, then DB write:** crash after the publish but before
  the DB commit → downstream consumers see an event for a point that
  was never actually persisted. A phantom event.

This is the general "dual write" problem, and no amount of retry logic
around either individual write fixes it — the two systems can't be made
to agree on outcome without a third piece of durable state coordinating
them.

## Decision
Use the **transactional outbox pattern**:
- Every processed message writes two rows in **one Postgres
  transaction**: the `TelemetryPoint` itself, and an `OutboxEvent` row
  (topic, key, JSON payload, `published_at = NULL`) — see
  `app/models/outbox.py`. Postgres's own transactional guarantee makes
  these two writes atomic; there's no dual-write problem left, because
  there's only one write (to one system).
- A separate, independent task — `outbox_relay.run()` — polls
  `outbox_events WHERE published_at IS NULL`, using
  `SELECT ... FOR UPDATE SKIP LOCKED` so multiple relay instances could
  run concurrently without double-publishing the same row, publishes
  each to Kafka, and marks it `published_at = now()` in the same
  transaction as the publish's local bookkeeping.
- If the relay crashes between publishing to Kafka and marking a row
  published, the row gets republished on restart — this is a conscious
  choice of **at-least-once** delivery, not exactly-once. Downstream
  consumers of `telemetry.processed` are expected to be idempotent
  (mirroring the same dedup discipline the processor itself uses on
  `telemetry.raw`), which is a strictly easier property to build than
  distributed exactly-once delivery.

## Alternatives considered
**Dual write with retry (write DB, then best-effort publish with
retries).** Rejected: retries reduce the failure window but don't close
it — a crash during the retry loop still loses the event, and this
approach has no durable record of "this publish still needs to happen"
that survives a process restart.

**Change Data Capture (Debezium reading the Postgres WAL).** A more
"automatic" version of the same idea — no application code writes an
outbox row explicitly. Rejected for this project's scope: it's a real,
production-grade option, but it adds a whole separate running system
(Debezium + Kafka Connect) to get something the explicit-outbox-row
approach already achieves with a table and a polling loop, at a
complexity cost this phase doesn't need to pay to demonstrate the
pattern correctly.

## Consequences
`outbox_events` grows unboundedly without a cleanup job for published
rows (not built yet — same category of gap as the refresh-token cleanup
noted in ADR-0003, flagged for the same later-phase backlog). The relay
introduces a publish-latency floor equal to its poll interval (1s); this
is an explicit throughput/latency tradeoff, not an oversight — tightening
it is a one-line change if a future phase needs it.
