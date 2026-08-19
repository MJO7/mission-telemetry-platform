"""
GET /ws/flights/{flight_id} -- live telemetry for one flight.

Every connection here does three things in order: authenticate (query
param token, see app/ws/auth.py), authorize (the flight must belong to
the caller's org -- same tenant-isolation rule as GET /v1/flights/{id},
just enforced by hand since this isn't an HTTP route with require_role
available), then register with the local ConnectionManager and, if it's
the first local watcher for this flight, subscribe this replica to its
Redis channel (see app/ws/fanout.py).
"""
import asyncio
import contextlib
import logging
import uuid

from fastapi import APIRouter, Depends, WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models.telemetry import Flight
from app.ws.auth import authenticate
from app.ws.manager import Connection

router = APIRouter(tags=["websocket"])
log = logging.getLogger("app.routers.telemetry_ws")

# Close codes in the 4000-4999 range are reserved for application use
# (RFC 6455) -- these never collide with the standard 1000-1015 codes a
# client's reconnect logic might special-case.
CLOSE_UNAUTHENTICATED = 4401
CLOSE_NOT_FOUND = 4404


async def _sender(websocket: WebSocket, conn: Connection) -> None:
    while True:
        message = await conn.queue.get()
        await websocket.send_text(message)


async def _watch_disconnect(websocket: WebSocket) -> None:
    # This connection is send-only from the server's perspective, but the
    # ASGI server still needs receive() pumped to notice the client went
    # away (a TCP close doesn't otherwise surface until something reads).
    while True:
        await websocket.receive_text()


@router.websocket("/ws/flights/{flight_id}")
async def flight_stream(
    websocket: WebSocket,
    flight_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    user = authenticate(websocket.query_params.get("token"))
    if user is None:
        await websocket.close(code=CLOSE_UNAUTHENTICATED)
        return

    result = await session.execute(
        select(Flight.id).where(Flight.id == flight_id, Flight.org_id == uuid.UUID(user.org_id))
    )
    if result.scalar_one_or_none() is None:
        # Same reasoning as the REST routes: 404-shaped, not 403-shaped --
        # don't confirm to a caller from another org that this ID exists.
        await websocket.close(code=CLOSE_NOT_FOUND)
        return

    await websocket.accept()

    manager = websocket.app.state.ws_manager
    fanout = websocket.app.state.ws_fanout
    fid = str(flight_id)

    conn, is_first = await manager.connect(fid, websocket)
    if is_first:
        await fanout.subscribe(fid)

    sender = asyncio.create_task(_sender(websocket, conn))
    receiver = asyncio.create_task(_watch_disconnect(websocket))
    try:
        done, pending = await asyncio.wait(
            {sender, receiver}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            # Retrieve whatever ended this connection (normal disconnect,
            # a send failure, ...) so asyncio doesn't log "exception was
            # never retrieved" for a task we're not propagating further.
            with contextlib.suppress(asyncio.CancelledError):
                task.exception()
    finally:
        is_last = await manager.disconnect(fid, conn)
        if is_last:
            await fanout.unsubscribe(fid)
