"""
Auth endpoints.

Refresh token transport: httpOnly + Secure + SameSite=Lax cookie, not the
JSON response body. Rationale (this is the whiteboard question the spec
flags): an httpOnly cookie is invisible to `document.cookie`, so a
successful XSS on the frontend cannot exfiltrate it -- it can still ride
along on requests via CSRF, which is why SameSite=Lax (blocks cross-site
POST) plus a same-origin API is the mitigating pair. localStorage is
readable by any injected script, which is strictly worse for the token
that's valid the longest (30 days here vs 10 minutes for the access
token, which we DO return in the body since it's short-lived and needed
in the Authorization header by design).
"""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.refresh import (
    RefreshTokenInvalid,
    RefreshTokenReused,
    issue_refresh_token,
    rotate_refresh_token,
)
from app.core.security import create_access_token, hash_password, verify_password
from app.models.tenancy import Organization, Role, User
from app.schemas.auth import LoginRequest, RegisterOrgRequest, TokenResponse

router = APIRouter(prefix="/v1/auth", tags=["auth"])
settings = get_settings()

REFRESH_COOKIE = "refresh_token"


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        raw_token,
        httponly=True,
        secure=settings.environment != "development",
        samesite="lax",
        max_age=settings.refresh_token_ttl_days * 86400,
        path="/v1/auth",
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_org(
    body: RegisterOrgRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    org = Organization(name=body.org_name, slug=body.org_name.lower().replace(" ", "-"))
    session.add(org)
    await session.flush()

    user = User(
        org_id=org.id,
        email=body.email,
        password_hash=hash_password(body.password),
        role=Role.owner,
    )
    session.add(user)
    await session.flush()

    access = create_access_token(user_id=user.id, org_id=org.id, role=user.role.value)
    raw_refresh, _ = await issue_refresh_token(session, user_id=user.id)
    await session.commit()

    _set_refresh_cookie(response, raw_refresh)
    return TokenResponse(access_token=access)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or user.password_hash is None or not verify_password(
        body.password, user.password_hash
    ):
        # Same error for "no such user" and "wrong password" -- don't
        # leak which one it was.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    access = create_access_token(user_id=user.id, org_id=user.org_id, role=user.role.value)
    raw_refresh, _ = await issue_refresh_token(session, user_id=user.id)
    await session.commit()

    _set_refresh_cookie(response, raw_refresh)
    return TokenResponse(access_token=access)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    session: AsyncSession = Depends(get_session),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
) -> TokenResponse:
    if refresh_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no refresh token")

    try:
        new_raw, row = await rotate_refresh_token(session, refresh_token)
    except RefreshTokenReused as exc:
        await session.commit()  # persist the family revocation
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "refresh token reuse detected"
        ) from exc
    except RefreshTokenInvalid as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh token") from exc

    result = await session.execute(select(User).where(User.id == row.user_id))
    user = result.scalar_one()
    access = create_access_token(user_id=user.id, org_id=user.org_id, role=user.role.value)
    await session.commit()

    _set_refresh_cookie(response, new_raw)
    return TokenResponse(access_token=access)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/v1/auth")
