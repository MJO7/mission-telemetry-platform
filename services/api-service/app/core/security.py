"""
Password hashing (argon2id) and JWT access-token issuance/verification.

Refresh tokens are handled in app/core/refresh.py -- they're not JWTs at
all (see that module's docstring for why).
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

settings = get_settings()

# Defaults (time_cost, memory_cost, parallelism) are argon2-cffi's
# OWASP-recommended baseline: 19 MiB, 2 iterations, 1 lane. Deliberately
# not hand-tuning this without a load test on real hardware -- guessing
# a "stronger" memory cost without measuring login latency under load is
# the kind of unmeasured complexity the spec says to flag.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(*, user_id: uuid.UUID, org_id: uuid.UUID, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Raises jwt.PyJWTError on expiry/tampering -- caller maps to 401."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return payload
