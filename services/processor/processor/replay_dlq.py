"""
Replay DLQ CLI: re-publishes payloads from telemetry.dlq back onto
telemetry.raw for reprocessing -- e.g. after fixing whatever caused the
original validation/processing failure (a firmware bug, a flight_id
that's since been created, etc.).

Deliberately a standalone script, not a service: replay is a human
decision made after looking at *why* something landed in the DLQ, not
something that should run unattended and automatically re-inject
previously-failed data.

Usage:
    python -m processor.replay_dlq            # replay everything currently queued
    python -m processor.replay_dlq --max 10    # replay at most 10 messages
"""
import argparse
import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from app.core.config import get_settings

log = logging.getLogger("processor.replay_dlq")
settings = get_settings()

DLQ_TOPIC = "telemetry.dlq"
RAW_TOPIC = "telemetry.raw"


async def replay(max_messages: int | None) -> int:
    consumer = AIOKafkaConsumer(
        DLQ_TOPIC,
        bootstrap_servers=settings.kafka_brokers,
        # A named, persistent group: each run only replays DLQ records
        # this tool hasn't already replayed, across invocations -- not
        # "replay everything in the topic, every single time."
        group_id="dlq-replay",
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_brokers)
    await consumer.start()
    await producer.start()
    replayed = 0
    try:
        while True:
            # getmany + a timeout, not `async for` -- this is a one-shot
            # CLI batch job that should exit once it's drained what's
            # currently queued, not a service that waits forever for the
            # next DLQ message to show up.
            batches = await consumer.getmany(timeout_ms=2000)
            if not batches:
                break
            for messages in batches.values():
                for msg in messages:
                    record = json.loads(msg.value)
                    payload = record["payload"]
                    body = json.dumps(payload).encode()
                    key = payload.get("vehicle_id") if isinstance(payload, dict) else None
                    await producer.send_and_wait(RAW_TOPIC, body, key=key.encode() if key else None)
                    replayed += 1
                    log.info("replayed dlq record (original reason: %s)", record.get("reason"))
                    if max_messages and replayed >= max_messages:
                        await consumer.commit()
                        return replayed
            await consumer.commit()
    finally:
        await consumer.stop()
        await producer.stop()
    return replayed


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Replay telemetry.dlq messages back onto telemetry.raw"
    )
    parser.add_argument("--max", type=int, default=None, help="stop after replaying N messages")
    args = parser.parse_args()
    n = asyncio.run(replay(args.max))
    print(f"replayed {n} message(s)")


if __name__ == "__main__":
    main()
