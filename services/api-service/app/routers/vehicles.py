import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.rbac import CurrentUser, require_role
from app.models.telemetry import Vehicle
from app.models.tenancy import Role
from app.schemas.telemetry import VehicleCreate, VehicleOut

router = APIRouter(prefix="/v1/vehicles", tags=["vehicles"])


@router.get("", response_model=list[VehicleOut])
async def list_vehicles(
    user: Annotated[CurrentUser, Depends(require_role(Role.viewer))],
    session: AsyncSession = Depends(get_session),
) -> list[Vehicle]:
    result = await session.execute(select(Vehicle).where(Vehicle.org_id == uuid.UUID(user.org_id)))
    return list(result.scalars().all())


@router.post("", response_model=VehicleOut, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    body: VehicleCreate,
    # Viewers are read-only per spec 3.1 -- creating a vehicle requires engineer+.
    user: Annotated[CurrentUser, Depends(require_role(Role.engineer))],
    session: AsyncSession = Depends(get_session),
) -> Vehicle:
    vehicle = Vehicle(org_id=uuid.UUID(user.org_id), name=body.name, description=body.description)
    session.add(vehicle)
    await session.commit()
    await session.refresh(vehicle)
    return vehicle


@router.get("/{vehicle_id}", response_model=VehicleOut)
async def get_vehicle(
    vehicle_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_role(Role.viewer))],
    session: AsyncSession = Depends(get_session),
) -> Vehicle:
    result = await session.execute(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.org_id == uuid.UUID(user.org_id))
    )
    vehicle = result.scalar_one_or_none()
    if vehicle is None:
        # 404, not 403 -- don't confirm to a caller from another org that
        # this ID exists at all.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "vehicle not found")
    return vehicle
