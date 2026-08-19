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
