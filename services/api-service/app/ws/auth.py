"""
WebSocket auth is not app/core/rbac.py's get_current_user -- that
dependency reads an `Authorization` header via HTTPBearer, and browsers'
native WebSocket API cannot set custom headers on the handshake at all.
The practical alternative (what real systems do here) is a short-lived
token on the query string, read once at connect time. It's the same JWT,
the same 10-minute TTL, and the same decode/verify path as everywhere
else -- just carried differently for this one handshake.
"""
import jwt

from app.core.security import decode_access_token
from app.models.tenancy import Role


class WSUser:
    def __init__(self, user_id: str, org_id: str, role: Role) -> None:
        self.user_id = user_id
        self.org_id = org_id
        self.role = role


def authenticate(token: str | None) -> WSUser | None:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        return None
    return WSUser(user_id=payload["sub"], org_id=payload["org_id"], role=Role(payload["role"]))
