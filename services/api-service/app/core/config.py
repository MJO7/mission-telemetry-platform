"""
Centralized settings via pydantic-settings.

Why: every service in this platform will eventually read config from env
vars (12-factor). Doing it through a typed Settings object instead of
scattered os.environ[...] calls means a missing/malformed env var fails
fast at startup with a clear error, not three requests deep into a
handler.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="API_")

    database_url: str = "postgresql+asyncpg://telemetry:telemetry@localhost:5432/telemetry"

    # JWT
    jwt_secret: str = "dev-secret-change-me-to-something-at-least-32-bytes-long"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 10
    refresh_token_ttl_days: int = 30

    environment: str = "development"

    # Explicit origin allowlist, not "*": the refresh cookie flow requires
    # allow_credentials=True on the CORS middleware, and browsers reject
    # allow_credentials paired with a wildcard origin outright (and it
    # would be the wrong call even if they didn't -- a same-origin-with-
    # cookies API shouldn't answer every origin on the internet). Vite's
    # dev server is the only caller in Phase 2; a deployed frontend's
    # origin gets added here via API_CORS_ORIGINS, not by loosening this.
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()