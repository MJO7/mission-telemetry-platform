"""
Async engine/session plus the tenant-scoping dependency.

This is "the single query dependency" the spec calls for: every router
that touches tenant data depends on `get_org_session`, which yields a
plain AsyncSession but also hands back the authenticated user's org_id.
Isolation is enforced by convention (every repository function takes
org_id and filters on it) rather than by the DB (see ADR-0001 for why
RLS was rejected). The honest caveat, worth saying out loud in an
interview: a handler that forgets to filter by org_id is a real bug this
design does not prevent. Centralizing session creation here at least
means there's one place to eventually bolt on a SQLAlchemy `do_orm_execute`
event listener that injects the filter automatically, if this ever needs
to become bulletproof.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
    # Explicit, not SQLAlchemy's defaults (pool_size=5, max_overflow=10
    # -- up to 15 connections per *pod*). That was invisible until a
    # real k8s HPA load test (k8s/README.md) scaled this Deployment to
    # 6 replicas under load and Postgres started rejecting new
    # connections outright (asyncpg.exceptions.TooManyConnectionsError:
    # "sorry, too many clients already") -- 6 pods x up to 15 each is
    # up to 90 connections from this service alone, before processor's
    # own pool or Postgres's reserved superuser slots. Bounding this
    # per-pod, in terms of "how many replicas could this realistically
    # scale to" rather than accepting whatever the default happens to
    # allow, is what makes the total connection count something anyone
    # can actually reason about against max_connections.
    pool_size=5,
    max_overflow=2,
    pool_timeout=10,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
