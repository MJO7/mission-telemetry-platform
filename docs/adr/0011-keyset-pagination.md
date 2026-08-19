# ADR-0011: Keyset pagination for telemetry history, not OFFSET/LIMIT

**Status:** Accepted — Phase 5

## Context
`GET /v1/flights/{id}/telemetry` returns however many raw points a
flight recorded — potentially millions for a long flight at a high
sample rate — a page at a time. Some way to say "give me the next page"
is required; the two well-known options are `OFFSET`/`LIMIT` and
keyset (a.k.a. "seek") pagination.

## Decision
Keyset pagination: each page's response includes an opaque `next_cursor`
(`app/core/pagination.py`, base64 over `(ts, seq_no)` of the last row
returned); the next request passes it back as `?after=`, and the query
becomes a `WHERE (ts, seq_no) > (cursor_ts, cursor_seq) ORDER BY ts,
seq_no LIMIT n` — a direct index seek on `ix_telemetry_points_flight_ts`
(`docs/adr/0010`), not a scan-and-discard.

Two reasons, both concrete for this specific table:
- **`OFFSET` gets slower with every page.** Postgres has to walk and
  discard every row before the offset to reach page 50 — for a table
  this can genuinely hold millions of rows for one flight, `OFFSET
  500000` is a real, measurable cost every single time, not a one-off.
  Keyset pagination's cost is the same for page 1 and page 50: an index
  seek plus `LIMIT` rows.
- **`OFFSET` is unstable under concurrent writes, and this table is
  never not being written to.** A flight being paged through by one
  request can simultaneously be receiving new points from Phase 3's
  processor. If a row is inserted with a `ts` before the current
  page's position, every subsequent `OFFSET`-based page shifts by one —
  a row can be skipped entirely or shown twice, silently, with no error
  to signal it happened. A keyset cursor is anchored to actual row
  values, not a position count, so it's immune to this: new rows
  inserted anywhere don't change what "after this specific point"
  means.

## Alternatives considered
**`OFFSET`/`LIMIT`, accepting the tradeoffs.** Rejected outright for
this specific table given both costs above are not theoretical here —
a live telemetry table under concurrent write load is close to the
textbook case keyset pagination exists for.

**Cursor as a raw, client-visible `(ts, seq_no)` pair instead of an
opaque encoded token.** Rejected: exposing the actual seek keys invites
a client to construct or mutate one by hand (e.g. to seek to a
timestamp that never fetched a real page), which works by accident today
but becomes a compatibility promise the moment it's relied on. Keeping
it opaque means the encoding can change later without being a breaking
API change.

## Consequences
There is no "jump to page 12" or "how many pages total" -- keyset
pagination only supports "give me the next page from here," which is
the right fit for a scrollable/streaming history view and the wrong fit
for a classic numbered-pages UI. Nothing in this system needs the
latter, so this isn't a real cost here, but it would be if a future
feature ever did.
