# ADR-0010: TimescaleDB hypertable + continuous aggregate for telemetry_points

**Status:** Accepted — Phase 5

## Context
`telemetry_points` is the one table in this system whose growth is
structurally different from every other: `Vehicle`/`Flight`/`User` grow
with how many *entities* exist, but `TelemetryPoint` grows with how much
*time* has been recorded across every flight ever ingested. At even
modest scale (a handful of vehicles, regular test flights, telemetry
sampled multiple times a second) this table reaches millions of rows
long before any other table reaches thousands. Two query shapes matter
against it: recent-heavy point lookups scoped to one flight (Phase 4's
live stream, and now Phase 5's paginated history endpoint), and
flight-level summaries (avg/max altitude, max acceleration) that a plain
`GROUP BY` over raw rows gets slower to compute the longer a flight ran.

## Decision
**Convert `telemetry_points` into a TimescaleDB hypertable**, partitioned
on `ts` in 1-day chunks (`docs/adr` migration `bc7e2855f65b`):
- Postgres itself already had everything else this project needs
  (JSON, full ACID transactions, the extension ecosystem) — Timescale is
  an extension on top of the same Postgres already running, not a
  second database to operate, back up, or reason about consistency
  against.
- Time-range queries prune whole chunks instead of scanning the full
  table (chunk exclusion) — the exact shape of the "one flight's
  history" and "live stream since reconnect" queries this system
  actually runs.
- Table maintenance (e.g. eventually dropping data older than a
  retention window) becomes `DROP` on whole chunks instead of a `DELETE`
  that has to find and remove scattered rows.

This required reshaping the table's constraints: Timescale requires the
partitioning column (`ts`) in every unique/PK constraint, so the PK
became composite `(id, ts)` and `uq_telemetry_flight_seq` grew to
`(flight_id, seq_no, ts)`. See `app/models/telemetry.py`'s
`TelemetryPoint` docstring for the honest accounting of what that
constraint change actually gives up (very little, in practice).

**Add a continuous aggregate**, `telemetry_1m`: a `time_bucket('1
minute', ts)` rollup per flight (avg/max altitude, avg/max velocity, max
acceleration, sample count), refreshed on a 1-minute policy. This is
what backs `GET /v1/flights/{id}/telemetry/summary` — an overview
query that would otherwise mean scanning every raw point of however
long a flight ran, every time someone wants to see its shape. See
`docs/BENCHMARKS.md` for the measured difference.

## Alternatives considered
**Vanilla Postgres with a hand-rolled monthly partition scheme
(`pg_partman` or manual `PARTITION BY RANGE`).** Rejected: this is
close to reinventing what Timescale already does, minus chunk-exclusion
tuning, minus continuous aggregates, minus the compression story
(Tier 2, not built yet) — for a maintenance burden that doesn't go away,
just moves to code this project would have to write and keep correct
itself.

**A dedicated time-series database (InfluxDB, Prometheus's TSDB).**
Rejected per the build spec's own governing constraint: introducing a
second database means a second thing to run, back up, and query
against, for data that has to join against `flights`/`vehicles` (both
plain relational tables) on almost every real query this system makes.
Timescale's whole pitch is not needing that split.

**Computing flight summaries at request time instead of a continuous
aggregate.** Rejected once measured: see `docs/BENCHMARKS.md` for the
real `EXPLAIN ANALYZE` difference between a live `GROUP BY` over raw
points and reading `telemetry_1m` directly.

## Consequences
The continuous aggregate is refreshed on a schedule (1 minute), not
synchronously with each insert — the summary endpoint can lag live
reality by up to that window. That's an accepted, named tradeoff, the
same shape as Phase 4's WS fan-out being explicitly at-most-once: the
summary endpoint is an overview, not the source of truth (raw
`telemetry_points`, and Phase 4's live stream for "right now", both
still are). There is no supported way to convert a hypertable back to a
plain table — the migration's `downgrade()` says so explicitly rather
than silently leaving the schema in a state this codebase never
actually runs against.
