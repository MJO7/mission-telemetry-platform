"""
RBAC as a FastAPI dependency, not a decorator.

`require_role(Role.engineer)` returns a dependency that resolves the
current user from the access token AND checks the role, so a route
declares its own requirement (`Depends(require_role(Role.engineer))`)
right in the signature -- visible in the OpenAPI docs and in the
function signature at the same time, instead of a separate decorator
that FastAPI's dependency-injection/testing tools don't know about.
"""
from collections.abc import Awaitable, Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.models.tenancy import Role

_bearer = HTTPBearer(auto_error=False)

# owner > engineer > viewer. A role satisfies a requirement if it's at
# or above the required rank.
_RANK = {Role.viewer: 0, Role.engineer: 1, Role.owner: 2}


class CurrentUser:
    def __init__(self, user_id: str, org_id: str, role: Role) -> None:
        self.user_id = user_id
        self.org_id = org_id
        self.role = role


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token") from exc
    return CurrentUser(user_id=payload["sub"], org_id=payload["org_id"], role=Role(payload["role"]))


def require_role(minimum: Role) -> Callable[[CurrentUser], Awaitable[CurrentUser]]:
    async def _dep(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if _RANK[user.role] < _RANK[minimum]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"requires role >= {minimum.value}, have {user.role.value}",
            )
        return user

    return _dep
