import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import engine
from app.routers import auth, flights, telemetry, telemetry_ws, vehicles
from app.ws.fanout import RedisFanout
from app.ws.kafka_bridge import KafkaToRedisBridge, run_forever
from app.ws.manager import ConnectionManager

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Phase 4: the WebSocket fan-out stack lives here, not as
    # module-level globals -- lifespan is the one place that runs
    # exactly once per process and can cleanly tear itself back down,
    # which matters for tests spinning up/tearing down the app repeatedly.
    manager = ConnectionManager(settings.ws_queue_maxsize)
    fanout = RedisFanout(settings.redis_url, manager)
    bridge = KafkaToRedisBridge(settings.kafka_brokers, settings.redis_url)

    await fanout.start()
    bridge_task = asyncio.create_task(run_forever(bridge))

    app.state.ws_manager = manager
    app.state.ws_fanout = fanout

    try:
        yield
    finally:
        bridge_task.cancel()
        try:
            await bridge_task
        except asyncio.CancelledError:
            pass
        await fanout.stop()


app = FastAPI(
    title="Mission Telemetry Platform API",
    version="0.1.0",
    # /v1 prefix lives on each router (spec 3.7: API versioning under /v1/)
    lifespan=lifespan,
)

# allow_credentials=True is required so the browser actually sends/stores
# the httpOnly refresh_token cookie on cross-origin requests from the SPA
# (Phase 2, web/) -- without it, the cookie set by /v1/auth/login would
# just be silently dropped by the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(vehicles.router)
app.include_router(flights.router)
app.include_router(telemetry.router)
app.include_router(telemetry_ws.router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness only: is the process up? No dependency checks here on
    purpose -- a DB blip shouldn't make an orchestrator kill and restart
    an otherwise-healthy process (that would compound an outage: the
    DB comes back, but now every pod is also cycling through a restart).
    That's what /readyz is for."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(response: Response) -> dict[str, str]:
    """Readiness, not liveness: can this replica actually serve traffic
    right now? Gated on a real round trip to Postgres, not just "is the
    process alive" -- the distinction a k8s readinessProbe exists for.
    A replica that can't reach its DB should be pulled out of the
    Service's endpoint list (no traffic routed to it) without being
    killed and restarted (liveness's job, and the wrong tool here: the
    process itself is fine, restarting it fixes nothing about the DB
    being unreachable).
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not ready", "reason": "database unreachable"}
    return {"status": "ready"}


@app.get("/v1/ws/stats")
async def ws_stats() -> dict[str, int]:
    """This replica's local WebSocket fan-out state -- how many flights
    it's watching, how many browsers are attached, how many messages
    it's had to drop under backpressure. Per-replica on purpose (not
    cluster-wide): each replica only knows about its own connections,
    which is itself the point being demonstrated (see docs/adr/0009)."""
    manager: ConnectionManager = app.state.ws_manager
    return manager.stats()
