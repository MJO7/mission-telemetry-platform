"""
Polls outbox_events for unpublished rows and produces them to Kafka --
the second half of the transactional outbox pattern (see
app/models/outbox.py in api-service for the full rationale). Runs as its
own asyncio task alongside the consumer, not inside it: the relay's job
(get rows to Kafka) is independent of the consumer's (get Kafka messages
into rows), and coupling them would mean a slow Kafka produce here
blocks new messages from being consumed, or vice versa.
"""
import asyncio
import logging
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models.outbox import OutboxEvent
from sqlalchemy import select

log = logging.getLogger("processor.outbox_relay")
settings = get_settings()

POLL_INTERVAL_SECONDS = 1.0
BATCH_SIZE = 100


async def _publish_batch(producer: AIOKafkaProducer) -> int:
    async with SessionLocal() as session:
        result = await session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at)
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        rows = list(result.scalars().all())
        if not rows:
            return 0

        for row in rows:
            await producer.send_and_wait(row.topic, row.payload.encode(), key=row.key.encode())
            row.published_at = datetime.now(timezone.utc)
        await session.commit()
        return len(rows)


async def run() -> None:
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_brokers)
    await producer.start()
    log.info("outbox relay started, polling every %.1fs", POLL_INTERVAL_SECONDS)
    try:
        while True:
            published = await _publish_batch(producer)
            if published:
                log.info("published %d outbox event(s)", published)
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
    finally:
        await producer.stop()
