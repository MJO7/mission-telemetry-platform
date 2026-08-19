"""
Tracks this replica's locally-connected WebSocket clients, grouped by
flight_id, and owns each connection's bounded outbound queue.

This is deliberately the *only* place that knows about actual
WebSocket objects. fanout.py and kafka_bridge.py only ever hand this
class a flight_id and a message string -- they have no idea how many
browsers are watching, or which replica they're connected to. That
split is what makes the fan-out story work: Kafka delivers an event to
exactly one replica's consumer instance, Redis fans it out to every
replica, and this class decides what "every replica" means locally.
"""
import asyncio
import logging

from fastapi import WebSocket

log = logging.getLogger("app.ws.manager")


class Connection:
    """One browser tab's WebSocket, wrapped with its own outbound queue.

    Backpressure policy: bounded queue, drop-newest-on-full. A slow or
    backgrounded tab falls behind; rather than buffer indefinitely (OOM
    risk under load) or block the fast path (one slow browser stalling
    Kafka consumption for everyone), new messages for that one
    connection are simply dropped once its queue is full. The client
    finds out it missed something the next time it re-fetches
    authoritative state (REST), not from this stream -- this stream is
    a live nice-to-have, not the durability path (that's Postgres +
    the outbox, see docs/adr/0008).
    """

    def __init__(self, websocket: WebSocket, maxsize: int) -> None:
        self.websocket = websocket
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=maxsize)
        self.dropped = 0


class ConnectionManager:
    def __init__(self, queue_maxsize: int) -> None:
        self._queue_maxsize = queue_maxsize
        self._by_flight: dict[str, set[Connection]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, flight_id: str, websocket: WebSocket) -> tuple[Connection, bool]:
        """Registers the connection; returns (conn, is_first_for_this_flight)
        so the caller knows whether it needs to Redis-SUBSCRIBE."""
        conn = Connection(websocket, self._queue_maxsize)
        async with self._lock:
            existing = self._by_flight.setdefault(flight_id, set())
            is_first = len(existing) == 0
            existing.add(conn)
        return conn, is_first

    async def disconnect(self, flight_id: str, conn: Connection) -> bool:
        """Unregisters the connection; returns True if it was the last one
        for this flight (caller should Redis-UNSUBSCRIBE)."""
        async with self._lock:
            existing = self._by_flight.get(flight_id)
            if existing is None:
                return False
            existing.discard(conn)
            is_last = len(existing) == 0
            if is_last:
                del self._by_flight[flight_id]
        return is_last

    def broadcast_local(self, flight_id: str, message: str) -> None:
        """Fans a message out to every connection this replica holds for
        `flight_id`. Synchronous and non-blocking on purpose -- queueing
        must never itself wait on a slow consumer (that's the whole
        point of the bounded queue + drop policy)."""
        for conn in self._by_flight.get(flight_id, ()):
            try:
                conn.queue.put_nowait(message)
            except asyncio.QueueFull:
                conn.dropped += 1
                if conn.dropped == 1 or conn.dropped % 50 == 0:
                    log.warning(
                        "slow consumer on flight %s, dropped=%d", flight_id, conn.dropped
                    )

    def stats(self) -> dict[str, int]:
        return {
            "flights_watched": len(self._by_flight),
            "connections": sum(len(conns) for conns in self._by_flight.values()),
            "dropped_total": sum(c.dropped for conns in self._by_flight.values() for c in conns),
        }
