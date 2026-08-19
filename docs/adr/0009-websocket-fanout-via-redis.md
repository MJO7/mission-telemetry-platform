# ADR-0009: Redis pub/sub for cross-replica WebSocket fan-out

**Status:** Accepted — Phase 4

## Context
Browsers watch a flight's telemetry live over WebSocket
(`GET /ws/flights/{id}`, served by api-service). api-service runs as
multiple replicas behind a load balancer, so two browsers watching the
*same* flight can land their WebSocket connections on *different*
replicas — there is no guarantee, and no reason to force one, that
"who's watching this flight" and "which replica processed this flight's
latest Kafka message" are ever the same process.

That means a naive "consume telemetry.processed, push straight to my
own WebSocket connections" implementation is wrong the moment there's
more than one replica: whichever replica's Kafka consumer instance a
given message lands on (ordinary consumer-group partition assignment,
same mechanics as Phase 3's processor) would only be able to reach
*its own* locally-connected browsers, silently leaving every browser
connected to a different replica with no update at all.

## Decision
Split the path in two, each solving a different half of the problem:

1. **Kafka → Redis** (`app/ws/kafka_bridge.py`): every api-service
   replica shares one consumer group, `api-ws-fanout`, reading
   `telemetry.processed`. Kafka's normal group mechanics hand each
   message to exactly one replica's consumer instance — same as any
   consumer group. That replica does a single Redis `PUBLISH` onto a
   per-flight channel (`telemetry:flight:{id}`).
2. **Redis → browsers** (`app/ws/fanout.py` + `app/ws/manager.py`):
   every replica keeps its own Redis `SUBSCRIBE` connection, joining
   exactly the per-flight channels it has local WebSocket watchers for
   (subscribe on the first local watcher, unsubscribe on the last).
   Redis's pub/sub broadcast semantics deliver that one `PUBLISH` to
   every subscribed replica — cross-process, cross-replica — regardless
   of which replica actually did the Kafka consuming.

The net effect: Kafka guarantees the event is consumed exactly once
*within the group*; Redis guarantees it's fanned out to *every*
replica that needs it. Neither system alone solves this — Kafka's
consumer groups are explicitly a *partitioning* primitive (one
consumer per partition), the opposite of what a broadcast needs; Redis
pub/sub alone has no durability or replay story, which is fine here
specifically because it never needs one (see the backpressure note
below).

**Backpressure:** each WebSocket connection has its own bounded
outbound queue (`ws_queue_maxsize`, default 100). A slow or
backgrounded browser tab that can't keep up gets its *new* messages
dropped once the queue is full — not buffered without limit (unbounded
memory growth under load) and not allowed to block delivery to every
other connection on the same replica (one slow tab must never stall
the rest). `GET /v1/ws/stats` exposes each replica's local drop count.

**At-most-once, on purpose:** the Kafka→Redis bridge auto-commits with
no dedup and no outbox. A crash that loses or double-delivers one live
tick is a non-event — the browser sees a small gap or a harmless
repeat, and can always re-fetch authoritative state over REST. This is
only an acceptable tradeoff *because* this path is not the system of
record; `telemetry_points` + the transactional outbox (Phase 3,
ADR-0008) already are, and always finish the durable write before this
path even sees the event.

**Client reconnect:** full-jitter exponential backoff
(`web/src/ws/backoff.ts`), capped at 15s, re-authenticating with a
fresh access token on every attempt. Plain (non-jittered) exponential
backoff was rejected: every client that dropped at the same instant
(e.g. an API replica restarting) would retry on the same schedule,
turning "the server came back up" into a synchronized burst of
reconnect attempts against it. Spreading each client's retry
uniformly across the whole backoff window avoids that.

## Alternatives considered
**Sticky sessions (route a browser to the same replica every time) +
in-process pub/sub only.** Rejected: it doesn't remove the problem, it
just narrows the window it happens in (a client still moves replicas
on any reconnect, deploy, or LB rebalance), while adding real
operational cost (session affinity at the LB) to a distributed system
that's supposed to demonstrate replicas *not* needing to know about
each other.

**A message broker for fan-out instead of Redis (a second Kafka topic
per flight, or NATS).** Rejected as solving a problem Redis already
solves for less: this fan-out is inherently ephemeral (a browser that
wasn't connected a second ago was never going to see that message
anyway), so pub/sub's total lack of persistence is a feature, not a
gap — and Redis is already a running dependency (Phase 3's dedup
store), not a new piece of infrastructure to justify.

**WebSocket auth via a header instead of a query-string token.**
Rejected: not actually available -- browsers' native WebSocket API
cannot set custom headers on the handshake at all, so a query
parameter (the same short-lived, 10-minute access token used
everywhere else) is the practical option, not a weaker one chosen for
convenience.

## Consequences
Every api-service replica now runs a background Kafka consumer
whether or not it currently has any WebSocket clients — a small,
constant cost accepted for topology simplicity (no separate fan-out
service, staying within the project's 4-service budget). A flight with
zero watchers on every replica means nobody is subscribed to its Redis
channel, so its `PUBLISH`es are simply dropped by Redis with nobody
listening — expected, and cheap, not a bug.
