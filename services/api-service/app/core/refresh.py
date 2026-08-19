"""
Refresh token issuance, rotation, and replay detection.

Why not just a longer-lived JWT? A JWT is unrevocable without a
blocklist you check on every request -- at which point you've built a
server-side token store anyway, just for the wrong token. So the
refresh token is opaque (a random 256-bit value), returned to the client
once, and only its SHA-256 hash is stored -- a DB leak doesn't hand out
usable tokens.

Rotation + replay detection: every refresh both consumes the presented
token and issues a new one in the same `family_id`. If a token is
presented that's already marked `rotated_at`, that's a signal the
token was stolen and used out of order (a legitimate client would have
gotten -- and used -- the newer one). We respond by revoking the entire
family, forcing re-login on all devices sharing that login session. This
is the standard rotation-with-reuse-detection scheme (used by e.g. Auth0);
the alternative -- a single long-lived non-rotating refresh token -- has
no way to distinguish "attacker stole this" from "legitimate reuse".
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.tenancy import RefreshToken

settings = get_settings()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def issue_refresh_token(
    session: AsyncSession, *, user_id: uuid.UUID, family_id: uuid.UUID | None = None
) -> tuple[str, RefreshToken]:
    raw = secrets.token_urlsafe(32)
    row = RefreshToken(
        user_id=user_id,
        family_id=family_id or uuid.uuid4(),
        token_hash=_hash(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_ttl_days),
    )
    session.add(row)
    await session.flush()
    return raw, row


class RefreshTokenInvalid(Exception):
    pass


class RefreshTokenReused(Exception):
    """Raised when a rotated-out token is presented again -- caller should
    revoke the session and force re-auth."""


async def rotate_refresh_token(
    session: AsyncSession, raw_token: str
) -> tuple[str, RefreshToken]:
    token_hash = _hash(raw_token)
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    row = result.scalar_one_or_none()

    if row is None:
        raise RefreshTokenInvalid()

    now = datetime.now(timezone.utc)
    if row.revoked_at is not None or row.expires_at < now:
        raise RefreshTokenInvalid()

    if row.rotated_at is not None:
        # Reuse of an already-rotated token: revoke the whole family.
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == row.family_id)
            .values(revoked_at=now)
        )
        raise RefreshTokenReused()

    row.rotated_at = now
    new_raw, new_row = await issue_refresh_token(
        session, user_id=row.user_id, family_id=row.family_id
    )
    return new_raw, new_row
