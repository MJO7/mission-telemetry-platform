"""
Organization / User / RBAC.

Role is a plain string enum column, not a separate roles/permissions
table. Rejected the normalized permissions-table design (roles ->
permissions -> role_permissions) as premature: we have exactly three
roles with fixed, hardcoded capabilities (see app/core/rbac.py). A
join-table RBAC system is the right call the day a customer needs a
*custom* role -- building it now would be modeling a requirement nobody
has yet.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamped, UUIDPk


class Role(str, enum.Enum):
    owner = "owner"
    engineer = "engineer"
    viewer = "viewer"


class Organization(Base, UUIDPk, Timestamped):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), unique=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)

    users: Mapped[list["User"]] = relationship(back_populates="organization")


class User(Base, UUIDPk, Timestamped):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("org_id", "email", name="uq_user_org_email"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(320), index=True)
    # Nullable: users created via GitHub OAuth have no local password.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    github_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), default=Role.viewer)
    is_active: Mapped[bool] = mapped_column(default=True)

    organization: Mapped["Organization"] = relationship(back_populates="users")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")


class RefreshToken(Base, UUIDPk, Timestamped):
    """
    Opaque refresh tokens, stored hashed (never plaintext), with a
    `family_id` shared across all tokens issued from one original login.
    Rotation: each use creates a new row in the same family and marks
    this one `rotated_at`. If a token with `rotated_at` set is presented
    again, it's a replay -- revoke the whole family (see auth.py).
    """
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
