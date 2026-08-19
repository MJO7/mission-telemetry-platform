"""
Transactional outbox: how `processor` gets a processed telemetry point
into Postgres *and* announced on Kafka without a dual-write bug.

The problem this exists to solve: processor's write path needs to (a)
persist a processed TelemetryPoint and (b) publish a "this point is
processed" event to telemetry.processed for alert-engine (Phase 7) to
react to. Doing those as two independent writes -- one to Postgres, one
to Kafka -- has no atomicity: a crash between them either loses the
Kafka event (data durably stored, nobody ever told) or, if Kafka is
written first, publishes an event for data that was never actually
committed.

The fix: processor writes the TelemetryPoint row *and* an OutboxEvent
row in the same Postgres transaction. Atomicity is free here because
it's one transaction in one database. A separate lightweight poller
(app in the processor service, not here) reads unpublished rows,
produces them to Kafka, and marks them published. If the poller crashes
mid-publish, the row is still sitting there unpublished -- it just
resumes, no data lost, no duplicate risk beyond the at-least-once
delivery Kafka already implies (which the consumer side already has to
handle via idempotent dedup, so this doesn't add a new failure mode).

Deliberately a polling relay, not Postgres LISTEN/NOTIFY or a CDC tool
like Debezium: those cut the publish latency from ~1s to ~0, but that's
new infrastructure this project doesn't need yet, for a latency nobody
has asked for. Revisit if Phase 7's alerting ever needs sub-second
telemetry-to-alert latency.
"""
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPk


class OutboxEvent(Base, UUIDPk, Timestamped):
    __tablename__ = "outbox_events"

    # The Kafka topic/key this row should be published as -- keeping
    # both here (rather than hardcoding "telemetry.processed" in the
    # relay) means the same outbox mechanism works for any future
    # event type without a schema change.
    topic: Mapped[str] = mapped_column(String(200))
    key: Mapped[str] = mapped_column(String(200))  # partition key, e.g. vehicle_id
    payload: Mapped[str] = mapped_column(Text)  # JSON-encoded event body

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
