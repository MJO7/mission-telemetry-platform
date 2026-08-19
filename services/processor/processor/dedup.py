"""
Idempotent delivery via Redis SETNX + TTL.

Kafka gives this consumer group at-least-once delivery: a message can be
redelivered after a crash between processing it and committing its
offset (see consumer.py's `run()` for exactly when that commit happens
relative to the DB write). SETNX turns "have I already handled this
exact packet" into one atomic check -- if the key already existed, some
earlier delivery already processed it, so this one is skipped instead of
double-inserted.

The TTL keeps the dedup set from growing forever; a duplicate that shows
up after the window has expired has genuine double-processing risk from
Redis's side alone, which is why telemetry_points also carries a
DB-level unique constraint (uq_telemetry_flight_seq) as a second,
TTL-free line of defense -- see the docstring on that constraint.
"""
from redis.asyncio import Redis


def dedup_key(vehicle_id: str, flight_id: str, seq_no: int) -> str:
    return f"dedup:{vehicle_id}:{flight_id}:{seq_no}"


async def claim(redis: Redis, key: str, ttl_seconds: int = 3600) -> bool:
    """True if this call is the first to see `key` (caller should
    process the message); False if it's a duplicate (caller should skip
    it)."""
    return bool(await redis.set(key, "1", nx=True, ex=ttl_seconds))


async def release(redis: Redis, key: str) -> None:
    """Undo a claim() that turned out not to represent a successfully
    processed message -- e.g. the packet was invalid or a DB write
    failed and the message was routed to the DLQ instead. Without this,
    the dedup key would keep the DLQ replay CLI's re-published copy
    silently swallowed as a "duplicate" for the rest of the TTL window,
    even though nothing was ever actually written."""
    await redis.delete(key)
