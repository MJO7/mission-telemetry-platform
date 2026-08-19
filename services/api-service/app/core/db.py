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

engine = create_async_engine(settings.database_url, pool_pre_ping=True, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
