"""
The replica-to-replica half of the fan-out story.

kafka_bridge.py hands a single event to exactly one replica (whichever
one Kafka's consumer-group coordinator assigned that partition to).
That replica alone doing a Redis PUBLISH would only reach browsers
connected to *it*. RedisFanout is what turns that into "every replica's
locally-connected browsers, regardless of which one is watching Kafka
right now": every replica keeps its own Redis SUBSCRIBE connection,
dynamically subscribed to exactly the flights it has local watchers
for, and Redis's own broadcast semantics deliver one PUBLISH to every
subscriber -- cross-process, cross-replica -- for free.
"""
import asyncio
import logging

from redis.asyncio import Redis

from app.ws.channels import channel_for_flight, flight_id_from_channel
from app.ws.manager import ConnectionManager

log = logging.getLogger("app.ws.fanout")

# redis-py's PubSub has no live connection at all -- and get_message()
# raises -- until at least one subscribe() has happened. Nothing ever
# publishes here; it exists purely so the reader loop has a connection
# to poll from the moment this replica starts, before any browser has
# connected to give it a real per-flight channel to subscribe to.
_KEEPALIVE_CHANNEL = "telemetry:_fanout_keepalive"


class RedisFanout:
    def __init__(self, redis_url: str, manager: ConnectionManager) -> None:
        self._redis: Redis = Redis.from_url(redis_url)
        self._pubsub = self._redis.pubsub()
        self._manager = manager
        self._reader_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        await self._pubsub.subscribe(_KEEPALIVE_CHANNEL)
        self._reader_task = asyncio.create_task(self._reader())

    async def stop(self) -> None:
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        # redis-py gap: PubSub.aclose() has no return annotation upstream.
        await self._pubsub.aclose()  # type: ignore[no-untyped-call]
        await self._redis.aclose()

    async def subscribe(self, flight_id: str) -> None:
        await self._pubsub.subscribe(channel_for_flight(flight_id))

    async def unsubscribe(self, flight_id: str) -> None:
        await self._pubsub.unsubscribe(channel_for_flight(flight_id))

    async def _reader(self) -> None:
        # get_message polling (not `async for ... pubsub.listen()`) so a
        # subscribe()/unsubscribe() called concurrently from a WS handler
        # doesn't have to fight this loop for the connection -- redis-py's
        # listen() and subscribe() share one connection and don't mix well
        # from two different coroutines at once.
        while True:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("redis pubsub reader error, retrying")
                await asyncio.sleep(1.0)
                continue
            if message is None:
                continue
            flight_id = flight_id_from_channel(message["channel"].decode())
            self._manager.broadcast_local(flight_id, message["data"].decode())
