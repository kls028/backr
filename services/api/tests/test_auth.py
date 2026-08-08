"""Wallet extraction from Supabase Web3 claims.

The fixtures below are copied verbatim from a real Sign-In-With-Solana against
GoTrue, not invented. If Supabase changes the claim shape, these fail loudly
rather than silently storing the wrong string.
"""

from __future__ import annotations

from app.auth import _extract_wallet

ADDRESS = "3oyC4eDUg4EAac8XTP41qQDNSc3yu1B9z2jKjeGgwnxz"

REAL_CLAIMS = {
    "aud": "authenticated",
    "role": "authenticated",
    "sub": "0c04dd41-b512-4354-8ba6-9e0212f3e251",
    "user_metadata": {
        "custom_claims": {
            "address": ADDRESS,
            "chain": "solana",
            "domain": "localhost:5273",
            "network": "",
            "statement": "Sign in to sss-project.",
        },
        "email_verified": False,
        "phone_verified": False,
        "sub": f"web3:solana:{ADDRESS}",
    },
}


def test_extracts_address_from_custom_claims() -> None:
    assert _extract_wallet(REAL_CLAIMS) == ADDRESS


def test_never_returns_the_prefixed_subject() -> None:
    """`user_metadata.sub` is "web3:solana:<addr>" — returning it raw would
    violate the base58 CHECK constraint on profiles.wallet."""
    claims = {"user_metadata": {"sub": f"web3:solana:{ADDRESS}"}}
    assert _extract_wallet(claims) == ADDRESS
    assert not _extract_wallet(claims).startswith("web3:")  # type: ignore[union-attr]


def test_custom_claims_wins_over_sub() -> None:
    claims = {
        "user_metadata": {
            "custom_claims": {"address": ADDRESS},
            "sub": "web3:solana:SomeOtherAddressEntirely1111111111111111",
        }
    }
    assert _extract_wallet(claims) == ADDRESS


def test_missing_metadata_is_none() -> None:
    assert _extract_wallet({}) is None
    assert _extract_wallet({"user_metadata": None}) is None
    assert _extract_wallet({"user_metadata": {}}) is None
    # An email/password user has metadata but no wallet anywhere.
    assert _extract_wallet({"user_metadata": {"email_verified": True}}) is None
