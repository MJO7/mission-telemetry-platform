import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.rbac import CurrentUser, require_role
from app.models.telemetry import Flight, Vehicle
from app.models.tenancy import Role
from app.schemas.telemetry import FlightCreate, FlightOut

router = APIRouter(prefix="/v1/flights", tags=["flights"])


@router.get("", response_model=list[FlightOut])
async def list_flights(
    user: Annotated[CurrentUser, Depends(require_role(Role.viewer))],
    session: AsyncSession = Depends(get_session),
) -> list[Flight]:
    # Phase 1: full-table-per-org scan is fine at this data volume.
    # Phase 5 replaces this with keyset pagination once flight counts
    # actually grow past a page.
    result = await session.execute(
        select(Flight)
        .where(Flight.org_id == uuid.UUID(user.org_id))
        .order_by(Flight.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=FlightOut, status_code=status.HTTP_201_CREATED)
async def create_flight(
    body: FlightCreate,
    user: Annotated[CurrentUser, Depends(require_role(Role.engineer))],
    session: AsyncSession = Depends(get_session),
) -> Flight:
    org_id = uuid.UUID(user.org_id)
    vehicle = await session.execute(
        select(Vehicle).where(Vehicle.id == body.vehicle_id, Vehicle.org_id == org_id)
    )
    if vehicle.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "vehicle not found")

    flight = Flight(org_id=org_id, vehicle_id=body.vehicle_id, name=body.name)
    session.add(flight)
    await session.commit()
    await session.refresh(flight)
    return flight


@router.get("/{flight_id}", response_model=FlightOut)
async def get_flight(
    flight_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_role(Role.viewer))],
    session: AsyncSession = Depends(get_session),
) -> Flight:
    result = await session.execute(
        select(Flight).where(Flight.id == flight_id, Flight.org_id == uuid.UUID(user.org_id))
    )
    flight = result.scalar_one_or_none()
    if flight is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "flight not found")
    return flight


@router.delete("/{flight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flight(
    flight_id: uuid.UUID,
    # Viewers explicitly cannot delete flights (spec 3.1).
    user: Annotated[CurrentUser, Depends(require_role(Role.engineer))],
    session: AsyncSession = Depends(get_session),
) -> None:
    result = await session.execute(
        select(Flight).where(Flight.id == flight_id, Flight.org_id == uuid.UUID(user.org_id))
    )
    flight = result.scalar_one_or_none()
    if flight is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "flight not found")
    await session.delete(flight)
    await session.commit()
