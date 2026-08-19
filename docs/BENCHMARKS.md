# Benchmarks: Phase 5 query optimization

Every number and query plan below is real `EXPLAIN (ANALYZE, BUFFERS)`
output, captured against a live Postgres 16 + TimescaleDB 2.29.1
instance (`docker compose`, unmodified from what `make dev` starts) —
none of it is estimated or invented. Reproduce it yourself:

```
make dev              # if not already up
make migrate          # applies the Phase 5 hypertable migration
make benchmark-seed   # scripts/benchmark_seed.sql -- ~1M rows, ~10-15s
```

`benchmark_seed.sql` creates one "subject" flight
(`00000000-0000-0000-0000-0000000000f0`) with 500,000 points spanning
~13.9 hours at a 100ms sample rate, plus five "noise" flights with
100,000 points each, timestamps jittered into the *same* time range so
they land interleaved in the same hypertable chunks as the subject
flight. That interleaving matters: without it, the subject flight's
rows are the only occupants of their chunks and a plain time-ordered
scan finds them for free, which is not what a real multi-tenant table
looks like.

## 1. Keyset pagination: with vs. without the composite index

Query (the exact one `GET /v1/flights/{id}/telemetry` runs, see
`app/routers/telemetry.py` and ADR-0011):

```sql
SELECT * FROM telemetry_points
WHERE flight_id = '00000000-0000-0000-0000-0000000000f0'
ORDER BY ts, seq_no
LIMIT 500;
```

**With `ix_telemetry_points_flight_ts (flight_id, ts)`:**

```
Limit  (actual time=0.028..0.128 rows=500 loops=1)
  Buffers: shared hit=27
  ->  Incremental Sort (actual time=0.027..0.110 rows=500 loops=1)
        Presorted Key: telemetry_points.ts
        ->  Custom Scan (ChunkAppend) (actual time=0.010..0.069 rows=501 loops=1)
              ->  Index Scan using ix_telemetry_points_flight_ts on _hyper_1_3_chunk
                    Index Cond: (flight_id = '...f0'::uuid)
                    Buffers: shared hit=18
Planning Time: 0.586 ms
Execution Time: 0.153 ms
```

**Same query, index dropped** (`DROP INDEX ix_telemetry_points_flight_ts`):

```
Limit  (actual time=0.066..0.418 rows=500 loops=1)
  Buffers: shared hit=1139
  ->  Incremental Sort (actual time=0.066..0.394 rows=500 loops=1)
        Presorted Key: telemetry_points.ts
        ->  Custom Scan (ChunkAppend) (actual time=0.019..0.345 rows=501 loops=1)
              ->  Index Scan Backward using telemetry_points_ts_idx on _hyper_1_3_chunk
                    Filter: (flight_id = '...f0'::uuid)
                    Rows Removed by Filter: 2500
                    Buffers: shared hit=1130
Planning Time: 0.649 ms
Execution Time: 0.446 ms
```

| | Buffers (shared hit) | Execution time |
|---|---|---|
| With composite index | 27 | 0.153 ms |
| Without (falls back to the ts-only index + a row filter) | 1139 | 0.446 ms |

**~42x fewer buffer touches, ~2.9x faster wall-clock, at 1M rows.**
Buffer count, not wall-clock, is the metric that actually matters here:
without the index, Postgres finds the right chunk via `ts` ordering but
then has to walk and discard every non-matching row along the way
(`Rows Removed by Filter: 2500` just to fill *one* 500-row page) — that
count scales with total table size, not with how many rows the query
actually wants. Wall-clock at 1M rows is already measurably worse; at
real production scale (the whole reason this table is a hypertable
partitioned for growth) the gap widens, not narrows.

## 2. Flight summary: continuous aggregate vs. live `GROUP BY`

Query (what `GET /v1/flights/{id}/telemetry/summary` runs against
`telemetry_1m`, vs. the equivalent computed live over raw points — see
ADR-0010):

**Via the `telemetry_1m` continuous aggregate:**

```
Custom Scan (ChunkAppend) on _materialized_hypertable_2  (actual time=0.038..0.272 rows=834 loops=1)
  Buffers: shared hit=53
  ->  Index Scan Backward using ..._flight_id_bucket_id on _hyper_2_4_chunk
        Index Cond: (flight_id = '...f0'::uuid)
Planning Time: 0.991 ms
Execution Time: 0.328 ms
```

**Live `GROUP BY time_bucket('1 minute', ts)` over raw `telemetry_points`:**

```
Finalize GroupAggregate  (actual time=0.278..73.307 rows=834 loops=1)
  Buffers: shared hit=10205 read=2467
  ->  Partial GroupAggregate
        ->  Index Scan using ix_telemetry_points_flight_ts on _hyper_1_3_chunk
              Index Cond: (flight_id = '...f0'::uuid)
              (actual time=0.025..44.462 rows=500000 loops=1)
Planning Time: 0.755 ms
Execution Time: 73.385 ms
```

| | Buffers (hit + read) | Execution time |
|---|---|---|
| `telemetry_1m` (continuous aggregate) | 53 | 0.328 ms |
| Live `GROUP BY` over 500k raw points | 12,672 | 73.385 ms |

**~224x faster, ~239x fewer buffer touches.** The live query has to
read all 500,000 of the subject flight's raw rows to produce the same
834 per-minute buckets the continuous aggregate already has sitting
pre-computed. This is the whole argument for a continuous aggregate in
one number: the cost of "show me this flight's shape" stops being
proportional to how long the flight was.

**Tradeoff, stated plainly (see ADR-0010's Consequences):** the
aggregate refreshes on a 1-minute policy, not synchronously with each
insert. A summary can lag up to that window behind the raw table. For
an overview chart, that's the right tradeoff; for "what is this
flight's *exact current* state," Phase 4's live WebSocket stream and
the raw `telemetry_points` table are what to use, not this endpoint.

## Methodology notes

- Postgres 16, TimescaleDB 2.29.1, running in the project's own
  `docker compose` (`timescale/timescaledb-ha:pg16`) — no tuned
  `postgresql.conf`, no dedicated benchmark hardware. These are the
  numbers this project's own dev stack produces, not a best-case lab
  setup.
- `ANALYZE telemetry_points` was run after seeding, before every
  capture, so the planner's row-count estimates reflect real table
  statistics.
- Each query was run once per plan shown above (not median-of-N) --
  appropriate for what's being demonstrated (which plan the optimizer
  picks, and the buffer-access-count difference between them, which
  doesn't have query-to-query variance the way wall-clock timing can).
  The wall-clock numbers are real single-run `EXPLAIN ANALYZE` output,
  not synthetic.
