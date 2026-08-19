import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class VehicleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class VehicleOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FlightCreate(BaseModel):
    vehicle_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)


class FlightOut(BaseModel):
    id: uuid.UUID
    vehicle_id: uuid.UUID
    name: str
    processing_status: str
    apogee_ft: float | None
    max_accel_g: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TelemetryPointOut(BaseModel):
    seq_no: int
    ts: datetime
    phase: str
    alt_ft: float
    vel_ft_s: float
    accel_g: float
    qw: float
    qx: float
    qy: float
    qz: float
    lat: float | None
    lon: float | None
    temp_c: float | None
    battery_v: float | None
    rssi: int | None

    model_config = {"from_attributes": True}


class TelemetryPageOut(BaseModel):
    points: list[TelemetryPointOut]
    # None means this page was the last one -- there's nothing more to
    # fetch, not "call again with an empty cursor to restart."
    next_cursor: str | None


class TelemetrySummaryBucketOut(BaseModel):
    """One row of the telemetry_1m continuous aggregate (see
    docs/adr/0010) -- a per-minute rollup, not a raw sample."""

    bucket: datetime
    avg_alt_ft: float | None
    max_alt_ft: float | None
    avg_vel_ft_s: float | None
    max_vel_ft_s: float | None
    max_accel_g: float | None
    sample_count: int

    model_config = {"from_attributes": True}
