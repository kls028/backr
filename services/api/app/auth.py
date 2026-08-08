"""Verification of Supabase-issued JWTs.

The backend never mints tokens and never sees a private key. Supabase Auth
handles Sign-In-With-Solana and issues the JWT; our only job is to check the
signature and pull the caller's identity out of it.

Two signing schemes are supported:
  * asymmetric (current default) - verified against the project's JWKS endpoint
  * HS256 shared secret (legacy projects) - verified against SUPABASE_JWT_SECRET
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)

# GoTrue namespaces the Web3 identity subject as "web3:<chain>:<address>".
_WEB3_SUB_PREFIX = "web3:solana:"


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """The authenticated caller, as asserted by a verified Supabase JWT."""

    id: uuid.UUID
    wallet: str | None
    claims: dict[str, Any]


@lru_cache
def _jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    # PyJWKClient keeps its own TTL cache, so we hold one instance per URL
    # rather than refetching the key set on every request.
    return jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)


def _extract_wallet(claims: dict[str, Any]) -> str | None:
    """Pull the wallet address out of a Supabase Web3 token.

    Verified against a real Sign-In-With-Solana. The shape is:

        user_metadata.custom_claims.address = "<base58 address>"
        user_metadata.sub                   = "web3:solana:<base58 address>"

    Read custom_claims.address. `sub` is deliberately only a fallback and is
    stripped of its prefix first -- returning it raw would hand callers
    "web3:solana:7xKX..." where they expect an address, and that value fails the
    base58 CHECK constraint on profiles.wallet.
    """
    metadata = claims.get("user_metadata")
    if not isinstance(metadata, dict):
        return None

    custom = metadata.get("custom_claims")
    if isinstance(custom, dict):
        address = custom.get("address")
        if isinstance(address, str) and address:
            return address

    subject = metadata.get("sub")
    if isinstance(subject, str) and subject.startswith(_WEB3_SUB_PREFIX):
        return subject.removeprefix(_WEB3_SUB_PREFIX) or None

    return None


def decode_token(token: str, settings: Settings) -> dict[str, Any]:
    """Verify a JWT and return its claims, or raise 401."""
    # Inlined at each call site rather than hoisted to a local: PyJWT types this
    # as a TypedDict, and mypy only infers that from the literal in position.
    try:
        secret = settings.supabase_jwt_secret
        if secret is not None:
            claims = jwt.decode(
                token,
                secret.get_secret_value(),
                algorithms=["HS256"],
                audience=settings.supabase_jwt_audience,
                options={"require": ["exp", "sub"]},
            )
        else:
            signing_key = _jwks_client(settings.jwks_url).get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=settings.supabase_jwt_audience,
                issuer=settings.jwt_issuer,
                options={"require": ["exp", "sub"]},
            )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if not isinstance(claims, dict):  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token")

    return claims


async def require_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser:
    """FastAPI dependency: resolve the caller or reject the request."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = decode_token(credentials.credentials, settings)

    try:
        user_id = uuid.UUID(str(claims["sub"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject is not a valid user id",
        ) from exc

    return CurrentUser(id=user_id, wallet=_extract_wallet(claims), claims=claims)


CurrentUserDep = Annotated[CurrentUser, Depends(require_user)]
