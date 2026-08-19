from fastapi import FastAPI

from app.routers import auth, flights, vehicles

app = FastAPI(
    title="Mission Telemetry Platform API",
    version="0.1.0",
    # /v1 prefix lives on each router (spec 3.7: API versioning under /v1/)
)

app.include_router(auth.router)
app.include_router(vehicles.router)
app.include_router(flights.router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness only: is the process up? No dependency checks here on
    purpose -- a DB blip shouldn't make an orchestrator kill and restart
    an otherwise-healthy process. That's what /readyz is for (Phase 3+,
    once Redis/Kafka exist to check)."""
    return {"status": "ok"}
