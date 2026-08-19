"""
Phase 5: read access to a flight's telemetry, in two shapes for two
different jobs.

GET .../telemetry           -- raw points, keyset-paginated (docs/adr/0011).
                                For "give me exactly what was recorded":
                                a scrollable log, an export, replay.
GET .../telemetry/summary   -- per-minute rollups from the telemetry_1m
                                continuous aggregate (docs/adr/0010).
                                For "give me the shape of this flight":
                                an overview chart that shouldn't have to
                                scan however many raw points a long
                                flight has just to draw itself.

Both start from the same tenant-isolation check as the rest of the
flights routes: the flight must exist and belong to the caller's org,
looked up by hand here (not require_role's own dependency chain) because
that check also doubles as "does this flight_id exist at all" for the
telemetry queries that follow.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.pagination import decode_cursor, encode_cursor
from app.core.rbac import CurrentUser, require_role
from app.models.telemetry import Flight, TelemetryPoint
from app.models.tenancy import Role
from app.schemas.telemetry import TelemetryPageOut, TelemetryPointOut, TelemetrySummaryBucketOut

router = APIRouter(prefix="/v1/flights/{flight_id}/telemetry", tags=["telemetry"])


async def _get_owned_flight(
    flight_id: uuid.UUID, org_id: uuid.UUID, session: AsyncSession
) -> Flight:
    result = await session.execute(
        select(Flight).where(Flight.id == flight_id, Flight.org_id == org_id)
    )
    flight = result.scalar_one_or_none()
    if flight is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "flight not found")
    return flight


@router.get("", response_model=TelemetryPageOut)
async def list_telemetry(
    flight_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_role(Role.viewer))],
    session: AsyncSession = Depends(get_session),
    limit: int = Query(500, ge=1, le=2000),
    after: str | None = Query(
        None, description="Opaque cursor from a previous page's next_cursor"
    ),
) -> TelemetryPageOut:
    await _get_owned_flight(flight_id, uuid.UUID(user.org_id), session)

    stmt = (
        select(TelemetryPoint)
        .where(TelemetryPoint.flight_id == flight_id)
        .order_by(TelemetryPoint.ts, TelemetryPoint.seq_no)
        .limit(limit)
    )
    if after is not None:
        try:
            cursor_ts, cursor_seq = decode_cursor(after)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "malformed cursor") from exc
        # Seek past the cursor position, not merely equal-or-past: a
        # tuple comparison (ts, seq_no) > (cursor_ts, cursor_seq) is what
        # keyset pagination actually means -- the naive `ts > cursor_ts`
        # alone would silently skip every other row that shares the
        # cursor's exact timestamp.
        stmt = stmt.where(
            (TelemetryPoint.ts > cursor_ts)
            | ((TelemetryPoint.ts == cursor_ts) & (TelemetryPoint.seq_no > cursor_seq))
        )

    rows = list((await session.execute(stmt)).scalars().all())
    next_cursor = encode_cursor(rows[-1].ts, rows[-1].seq_no) if len(rows) == limit else None
    return TelemetryPageOut(
        points=[TelemetryPointOut.model_validate(r) for r in rows], next_cursor=next_cursor
    )


@router.get("/summary", response_model=list[TelemetrySummaryBucketOut])
async def telemetry_summary(
    flight_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_role(Role.viewer))],
    session: AsyncSession = Depends(get_session),
) -> list[TelemetrySummaryBucketOut]:
    await _get_owned_flight(flight_id, uuid.UUID(user.org_id), session)

    # telemetry_1m is a Timescale continuous aggregate (raw SQL DDL, see
    # the Phase 5 migration) -- not an ORM-mapped table, so this is a
    # plain query via text(), not the ORM. It carries flight_id but not
    # org_id (the aggregate's own GROUP BY), which is why the tenant
    # check above has to happen against Flight first.
    result = await session.execute(
        text(
            "SELECT bucket, avg_alt_ft, max_alt_ft, avg_vel_ft_s, max_vel_ft_s, "
            "max_accel_g, sample_count FROM telemetry_1m "
            "WHERE flight_id = :flight_id ORDER BY bucket"
        ),
        {"flight_id": str(flight_id)},
    )
    return [TelemetrySummaryBucketOut.model_validate(dict(row)) for row in result.mappings()]
