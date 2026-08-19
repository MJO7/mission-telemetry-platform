from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import auth, flights, vehicles

settings = get_settings()

app = FastAPI(
    title="Mission Telemetry Platform API",
    version="0.1.0",
    # /v1 prefix lives on each router (spec 3.7: API versioning under /v1/)
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


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness only: is the process up? No dependency checks here on
    purpose -- a DB blip shouldn't make an orchestrator kill and restart
    an otherwise-healthy process. That's what /readyz is for (Phase 3+,
    once Redis/Kafka exist to check)."""
    return {"status": "ok"}
