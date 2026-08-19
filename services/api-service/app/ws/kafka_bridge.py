"""
Consumes telemetry.processed and republishes each event onto its
flight's Redis channel -- the Kafka-to-Redis hop that starts the
fan-out chain (see fanout.py for the Redis-to-browsers half).

Deliberately its own consumer group ("api-ws-fanout"), separate from
processor's "processor-group": this is a completely independent
downstream reader of the same topic, not a replica of the group that
writes telemetry_points. Every api-service replica shares this ONE
group, so Kafka's normal consumer-group partition assignment sends
each message to exactly one replica -- which is what makes a single
Redis PUBLISH (not one per replica) correct. See docs/adr/0009.

Deliberately at-most-once here (auto-commit, no dedup, no outbox): a
crash that loses or double-delivers one live-stream tick is a
non-event -- the browser just sees a small gap or a harmless repeat,
and can always re-fetch authoritative state over REST. That tradeoff
is only safe *because* this bridge is not the durability path;
telemetry_points + the outbox (Phase 3) already are.
"""
import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
from redis.asyncio import Redis

from app.ws.channels import channel_for_flight

log = logging.getLogger("app.ws.kafka_bridge")

PROCESSED_TOPIC = "telemetry.processed"
GROUP_ID = "api-ws-fanout"


class KafkaToRedisBridge:
    def __init__(self, kafka_brokers: list[str], redis_url: str) -> None:
        self._kafka_brokers = kafka_brokers
        self._redis_url = redis_url

    async def run(self) -> None:
        consumer = AIOKafkaConsumer(
            PROCESSED_TOPIC,
            bootstrap_servers=self._kafka_brokers,
            group_id=GROUP_ID,
            enable_auto_commit=True,
            auto_offset_reset="latest",  # a live-updates stream cares about
            # "from now on", not replaying a backlog from before this
            # replica existed -- unlike processor's group, which starts
            # at "earliest" because it's writing the system of record.
        )
        redis: Redis = Redis.from_url(self._redis_url)
        await consumer.start()
        log.info("kafka->redis bridge started, group=%s topic=%s", GROUP_ID, PROCESSED_TOPIC)
        try:
            async for msg in consumer:
                try:
                    data = json.loads(msg.value)
                    flight_id = data["flight_id"]
                except (json.JSONDecodeError, KeyError):
                    log.warning("unparseable telemetry.processed record, skipping")
                    continue
                await redis.publish(channel_for_flight(flight_id), msg.value)
        finally:
            await consumer.stop()
            await redis.aclose()


async def run_forever(bridge: KafkaToRedisBridge) -> None:
    """Wraps run() with restart-on-crash: this bridge is a long-lived
    background task inside api-service's own process (see main.py's
    lifespan), not a supervised standalone process like processor -- if
    its Kafka connection drops, it should reconnect, not silently stop
    fanning out live updates for the rest of the app's uptime."""
    while True:
        try:
            await bridge.run()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("kafka->redis bridge crashed, restarting in 2s")
            await asyncio.sleep(2.0)
