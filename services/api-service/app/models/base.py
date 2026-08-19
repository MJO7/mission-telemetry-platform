"""
Declarative base + shared mixins.

Why UUID primary keys instead of serial/bigserial: multi-tenant rows get
created client-side in some future flow (e.g. idempotent flight creation
from the ingest path) and by ARQ workers concurrently with API requests.
UUIDs let any of those generate a collision-free PK without a round trip
to the DB for a sequence value. Cost: 16 bytes vs 8, and worse index
locality than a monotonic bigint -- acceptable here because our hottest
table (TelemetryPoint) is queried by (flight_id, ts), not by its own PK.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UUIDPk:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
