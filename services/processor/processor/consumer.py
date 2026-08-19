"""
Consumes telemetry.raw, dedupes via Redis, and writes each new point to
Postgres *plus* an outbox row in one transaction (see app/models/outbox.py
in api-service for why that pairing matters). Messages that fail to
process -- malformed JSON, a missing field, a flight_id that doesn't
exist -- are routed to telemetry.dlq instead of crashing the consumer
loop or being silently dropped.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models.outbox import OutboxEvent
from app.models.telemetry import FlightPhase, TelemetryPoint
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError

from .dedup import claim, dedup_key, release

log = logging.getLogger("processor.consumer")
settings = get_settings()

RAW_TOPIC = "telemetry.raw"
DLQ_TOPIC = "telemetry.dlq"
PROCESSED_TOPIC = "telemetry.processed"


def build_point(data: dict[str, Any]) -> TelemetryPoint:
    """Pure construction + validation -- raises KeyError/ValueError on
    bad data, does no I/O. Kept separate from _handle_message so it's
    unit testable without a database, Kafka, or Redis (mirrors
    ingest-service's Packet.Validate() split for the same reason)."""
    return TelemetryPoint(
        org_id=uuid.UUID(data["org_id"]),
        flight_id=uuid.UUID(data["flight_id"]),
        seq_no=data["seq_no"],
        ts=datetime.fromisoformat(data["ts"]),
        phase=FlightPhase(data["phase"]),
        alt_ft=data["alt_ft"],
        vel_ft_s=data["vel_ft_s"],
        accel_g=data["accel_g"],
        qw=data["qw"],
        qx=data["qx"],
        qy=data["qy"],
        qz=data["qz"],
        lat=data.get("lat"),
        lon=data.get("lon"),
        temp_c=data.get("temp_c"),
        battery_v=data.get("battery_v"),
        rssi=data.get("rssi"),
    )


async def _dlq(producer: AIOKafkaProducer, reason: str, raw: bytes, payload: Any = None) -> None:
    body = json.dumps(
        {
            "reason": reason,
            "payload": payload if payload is not None else raw.decode(errors="replace"),
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()
    await producer.send_and_wait(DLQ_TOPIC, body)


async def _handle_message(redis: Redis, producer: AIOKafkaProducer, raw: bytes) -> None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        await _dlq(producer, f"invalid JSON: {exc}", raw)
        return

    try:
        key = dedup_key(data["vehicle_id"], data["flight_id"], data["seq_no"])
    except KeyError as exc:
        await _dlq(producer, f"missing field: {exc}", raw, payload=data)
        return

    if not await claim(redis, key):
        log.info("duplicate skipped: %s", key)
        return

    try:
        point = build_point(data)
    except (KeyError, ValueError) as exc:
        # Release the claim: nothing was written, so a future replay of
        # this same message (after whatever caused the failure is fixed)
        # must be allowed to actually reach build_point() again instead
        # of being silently swallowed as a "duplicate" of an attempt
        # that never succeeded.
        await release(redis, key)
        await _dlq(producer, f"invalid packet: {exc}", raw, payload=data)
        return

    event_payload = json.dumps(
        {
            "vehicle_id": data["vehicle_id"],
            "flight_id": data["flight_id"],
            "seq_no": data["seq_no"],
            "phase": data["phase"],
            "alt_ft": data["alt_ft"],
            "ts": data["ts"],
        }
    )
    outbox_row = OutboxEvent(topic=PROCESSED_TOPIC, key=data["vehicle_id"], payload=event_payload)

    async with SessionLocal() as session:
        try:
            session.add(point)
            session.add(outbox_row)
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            # Most likely a flight_id (or org_id) that doesn't exist --
            # the FK constraint catching what build_point's plain UUID
            # parsing can't: syntactically valid, semantically wrong.
            # Release the claim for the same reason as the build_point
            # branch above: nothing was committed, so replay must reach
            # this code path again, not be dropped as a duplicate.
            await release(redis, key)
            log.warning("db error, routed to dlq: %s", exc.orig)
            await _dlq(producer, f"db error: {exc.orig}", raw, payload=data)


async def run() -> None:
    consumer = AIOKafkaConsumer(
        RAW_TOPIC,
        bootstrap_servers=settings.kafka_brokers,
        group_id="processor-group",
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_brokers)
    redis: Redis = Redis.from_url(settings.redis_url)

    await consumer.start()
    await producer.start()
    log.info("processor consumer started, group=processor-group topic=%s", RAW_TOPIC)
    try:
        async for msg in consumer:
            await _handle_message(redis, producer, msg.value)
            # Commit only after the message is durably handled (inserted,
            # deduped, or routed to DLQ) -- a crash before this line means
            # Kafka redelivers it on restart, which Redis's dedup then
            # turns into a safe no-op instead of a duplicate insert. This
            # is the concrete reason idempotent dedup exists at all: it's
            # what makes at-least-once delivery safe to build on.
            await consumer.commit()
    finally:
        await consumer.stop()
        await producer.stop()
        await redis.aclose()
