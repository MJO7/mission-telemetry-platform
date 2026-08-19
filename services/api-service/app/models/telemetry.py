"""
Vehicle / Flight / TelemetryPoint.

TelemetryPoint carries org_id directly (see base.py docstring rationale).
In Phase 5 this table becomes a Timescale hypertable and (ts, flight_id)
absorbs a composite index; for now it's a plain Postgres table so Phase 1
doesn't require the Timescale extension to be installed to run.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamped, UUIDPk


class FlightPhase(str, enum.Enum):
    pad = "pad"
    powered = "powered"
    coasting = "coasting"
    apogee = "apogee"
    drogue = "drogue"
    main = "main"
    landed = "landed"


class Vehicle(Base, UUIDPk, Timestamped):
    __tablename__ = "vehicles"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    flights: Mapped[list["Flight"]] = relationship(back_populates="vehicle")


class Flight(Base, UUIDPk, Timestamped):
    __tablename__ = "flights"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    apogee_ft: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_accel_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Set once the upload/fusion job (Phase 6) finishes; UI polls this.
    processing_status: Mapped[str] = mapped_column(String(32), default="pending")

    vehicle: Mapped["Vehicle"] = relationship(back_populates="flights")
    points: Mapped[list["TelemetryPoint"]] = relationship(back_populates="flight")


class TelemetryPoint(Base, UUIDPk):
    """
    No Timestamped mixin here on purpose: `created_at`/`updated_at` would
    be redundant with `ts` (the flight-relative sample time, which is
    what every query and index cares about) on a table that will hold
    10M+ rows. Two unused timestamp columns times 10M rows is real bytes.
    """
    __tablename__ = "telemetry_points"

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    flight_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("flights.id", ondelete="CASCADE"), index=True
    )
    seq_no: Mapped[int] = mapped_column(Integer)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    phase: Mapped[FlightPhase] = mapped_column(Enum(FlightPhase, name="flight_phase"))

    alt_ft: Mapped[float] = mapped_column(Float)
    vel_ft_s: Mapped[float] = mapped_column(Float)
    accel_g: Mapped[float] = mapped_column(Float)
    qw: Mapped[float] = mapped_column(Float)
    qx: Mapped[float] = mapped_column(Float)
    qy: Mapped[float] = mapped_column(Float)
    qz: Mapped[float] = mapped_column(Float)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery_v: Mapped[float | None] = mapped_column(Float, nullable=True)
    rssi: Mapped[int | None] = mapped_column(Integer, nullable=True)

    flight: Mapped["Flight"] = relationship(back_populates="points")
