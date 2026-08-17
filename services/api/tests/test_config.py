"""Configuration invariants that authentication depends on.

Both cases below produced the same symptom in practice — every authenticated
request returning `{"detail":"Invalid or expired token"}` — from two unrelated
causes, so both are pinned.
"""

from __future__ import annotations

from app.config import Settings


def test_blank_jwt_secret_is_treated_as_unset() -> None:
    """`SUPABASE_JWT_SECRET=` in .env must select the JWKS path, not HS256.

    An empty env var arrives as "", which pydantic wraps as SecretStr("").
    That is not None, so the verifier took the HS256 branch and rejected every
    ES256 token a modern Supabase project issues.
    """
    settings = Settings(supabase_jwt_secret="", helius_webhook_secret="   ")
    assert settings.supabase_jwt_secret is None
    assert settings.helius_webhook_secret is None


def test_a_real_jwt_secret_is_still_honoured() -> None:
    settings = Settings(supabase_jwt_secret="legacy-hs256-secret")
    assert settings.supabase_jwt_secret is not None
    assert settings.supabase_jwt_secret.get_secret_value() == "legacy-hs256-secret"


def test_issuer_comes_from_the_public_url_not_the_internal_one() -> None:
    """Tokens carry the browser-facing host in `iss`.

    The API reaches Supabase through the docker host gateway, so validating the
    issuer against supabase_url compares host.docker.internal to 127.0.0.1 and
    fails for every genuine token.
    """
    settings = Settings(
        supabase_url="http://host.docker.internal:54421",
        supabase_public_url="http://127.0.0.1:54421",
    )
    assert settings.jwt_issuer == "http://127.0.0.1:54421/auth/v1"
    # JWKS is fetched by the service itself, so it uses the internal address.
    assert settings.jwks_url == ("http://host.docker.internal:54421/auth/v1/.well-known/jwks.json")


def test_urls_tolerate_a_trailing_slash() -> None:
    settings = Settings(
        supabase_url="http://internal:54421/",
        supabase_public_url="http://127.0.0.1:54421/",
    )
    assert settings.jwt_issuer == "http://127.0.0.1:54421/auth/v1"
    assert settings.jwks_url.startswith("http://internal:54421/auth/v1")
