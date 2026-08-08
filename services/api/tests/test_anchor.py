"""Anchor encoding is load-bearing: a wrong discriminator is a runtime failure
with a useless error message, so pin the values."""

from __future__ import annotations

from app.solana.anchor import (
    account_discriminator,
    decode_u64,
    encode_string,
    encode_u64,
    instruction_discriminator,
)


def test_instruction_discriminator_is_stable() -> None:
    # sha256("global:initialize")[:8]
    assert instruction_discriminator("initialize").hex() == "afaf6d1f0d989bed"
    assert instruction_discriminator("increment").hex() == "0b12680968ae3b21"


def test_account_discriminator_differs_from_instruction() -> None:
    assert account_discriminator("Counter") != instruction_discriminator("counter")


def test_u64_roundtrip() -> None:
    for value in (0, 1, 2**63, 2**64 - 1):
        assert decode_u64(encode_u64(value)) == value


def test_u64_rejects_out_of_range() -> None:
    import pytest

    with pytest.raises(ValueError):
        encode_u64(2**64)
    with pytest.raises(ValueError):
        encode_u64(-1)


def test_borsh_string_is_length_prefixed() -> None:
    assert encode_string("ab") == b"\x02\x00\x00\x00ab"
    # Length is in bytes, not codepoints.
    assert encode_string("é") == b"\x02\x00\x00\x00\xc3\xa9"
