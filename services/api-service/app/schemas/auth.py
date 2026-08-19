import uuid

from pydantic import BaseModel, EmailStr, Field

from app.models.tenancy import Role


class RegisterOrgRequest(BaseModel):
    """First user of a brand-new org is always created as owner."""
    org_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # refresh_token is NOT included here -- it goes out as an httpOnly
    # cookie (see routers/auth.py), never in a JSON body a script could read.


class UserOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    role: Role

    model_config = {"from_attributes": True}
