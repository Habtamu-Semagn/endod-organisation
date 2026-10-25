"""Settings, read from the environment or ``.env``.

The names match deploy/.env.example: ORG_DATABASE_URL, SESSION_SECRET,
BFF_SHARED_SECRET and SITE_ORIGIN; the rest have safe defaults and are
prefixed ``ORG_``.
"""

from __future__ import annotations

from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Placeholder used only outside production when SESSION_SECRET is unset.
DEV_SESSION_SECRET = "dev-only-session-secret-change-me-0123456789"
#: The same for BFF_SHARED_SECRET (the web app's default in development).
DEV_BFF_SECRET = "dev-only-bff-secret-change-me-0123456789abcd"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ORG_ENVIRONMENT: str = "development"
    #: SQLAlchemy URL of this service's own database, e.g.
    #: ``postgresql+psycopg://org_app:pw@postgres:5432/organisation``.
    ORG_DATABASE_URL: Optional[str] = None
    #: Where receipt files are kept (a volume in production).
    ORG_RECEIPTS_DIR: str = "./receipts"

    #: Keys the hashes of session tokens, setup links and recovery codes, and
    #: encrypts TOTP secrets at rest (via HKDF, a separate key for each use).
    #: Changing it signs everyone out and voids every enrolled authenticator.
    SESSION_SECRET: Optional[str] = None
    #: Shared with the web app (its BFF sends it as X-BFF-Secret). Every request
    #: but /health without it is refused, so nothing else on the networks this
    #: API joins can call it, and only the BFF says who the client is.
    BFF_SHARED_SECRET: Optional[str] = None
    #: The portal's public origin; setup links point at it.
    SITE_ORIGIN: str = "http://localhost:3000"

    #: Sessions: idle timeout and absolute limit.
    ORG_SESSION_IDLE_MINUTES: int = 30
    ORG_SESSION_MAX_HOURS: int = 12
    #: A half-finished sign-in (password given, TOTP or enrolment pending).
    ORG_PENDING_SESSION_MINUTES: int = 15
    #: A fresh TOTP is needed this recently before approve, reject, mark paid
    #: and policy or payout changes.
    ORG_REAUTH_MINUTES: int = 10
    #: Setup links from ``create-admin`` / ``reset-2fa``.
    ORG_SETUP_LINK_HOURS: int = 24

    #: Failed sign-in steps against one account from one address before that
    #: pair is locked, and for how long.
    ORG_LOCKOUT_ATTEMPTS: int = 5
    ORG_LOCKOUT_MINUTES: int = 15
    #: Per-account backoff: from this many recent failures (any address),
    #: base * 2^(n - after) seconds, at most max; failures older than the window are forgotten.
    ORG_BACKOFF_AFTER: int = 3
    ORG_BACKOFF_BASE_SECONDS: int = 30
    ORG_BACKOFF_MAX_SECONDS: int = 900
    ORG_BACKOFF_WINDOW_MINUTES: int = 60
    #: Failed sign-in steps from one address within the window before it is refused (429).
    ORG_IP_FAILURE_LIMIT: int = 20
    ORG_IP_WINDOW_MINUTES: int = 15

    @field_validator("ORG_ENVIRONMENT", mode="before")
    @classmethod
    def _lower(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("SITE_ORIGIN", mode="before")
    @classmethod
    def _no_trailing_slash(cls, value):
        return value.strip().rstrip("/") if isinstance(value, str) else value

    @property
    def is_production(self) -> bool:
        return self.ORG_ENVIRONMENT == "production"

    def session_secret(self) -> str:
        secret = self.SESSION_SECRET or ""
        if len(secret) >= 32:
            return secret
        if self.is_production or secret:
            raise RuntimeError("SESSION_SECRET must be set to at least 32 random characters.")
        return DEV_SESSION_SECRET

    def bff_secret(self) -> str:
        secret = self.BFF_SHARED_SECRET or ""
        if len(secret) >= 32:
            return secret
        if self.is_production or secret:
            raise RuntimeError("BFF_SHARED_SECRET must be set to at least 32 random characters.")
        return DEV_BFF_SECRET


def get_settings() -> Settings:
    """Fresh each call: cheap, and tests can change the environment."""
    return Settings()
