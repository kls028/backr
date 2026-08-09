"""Runtime configuration, loaded from the environment.

Everything the service needs comes through here so tests can override a single
object instead of monkeypatching os.environ in a dozen places.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["local", "staging", "production"] = "local"
    log_level: str = "INFO"

    # --- HTTP ---------------------------------------------------------------
    # Vite dev server. Add your deployed origin in staging/production.
    cors_origins: list[str] = Field(default=["http://localhost:5273", "http://127.0.0.1:5273"])

    # --- Database -----------------------------------------------------------
    # Points at the Postgres inside the local `supabase start` stack by default.
    # From a container on macOS that host is host.docker.internal.
    # Ports are shifted off the Supabase defaults (5442x instead of 5432x)
    # because another local stack already holds 54321-54327 on this machine.
    # They must match supabase/config.toml.
    database_url: str = "postgresql+asyncpg://postgres:postgres@host.docker.internal:54422/postgres"
    db_pool_size: int = 5
    db_max_overflow: int = 5

    # --- Supabase auth ------------------------------------------------------
    supabase_url: str = "http://host.docker.internal:54421"
    # Legacy HS256 projects set this. Newer projects use asymmetric signing keys
    # and leave it empty, in which case we verify against the JWKS endpoint.
    supabase_jwt_secret: SecretStr | None = None
    supabase_jwt_audience: str = "authenticated"

    # --- Solana -------------------------------------------------------------
    solana_rpc_url: str = "http://host.docker.internal:8899"
    # Must match declare_id! in onchain/programs/sss_core/src/lib.rs.
    # `pnpm idl:sync` warns when .env has drifted from the built program.
    program_id: str = "5dzttAFNMi3JNtBcBQzJWcyXwou4rN2z6KX5DitDSDHe"
    # The deployment-specific USDC mint. Publication fails closed when unset.
    usdc_mint: str = ""
    success_bonus_rate_bps: int = 2_000
    active_subscription_limit_months: int = 12

    # --- Helius ingest ------------------------------------------------------
    # Shared secret Helius echoes back in the Authorization header. If unset the
    # webhook route refuses every request rather than accepting unauthenticated
    # writes — fail closed, not open.
    helius_webhook_secret: SecretStr | None = None

    # --- Reconciliation worker ---------------------------------------------
    reconcile_interval_seconds: int = 60
    reconcile_batch_size: int = 100

    @property
    def jwks_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    @property
    def jwt_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
