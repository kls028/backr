"""Minimal Anchor encoding helpers.

We do not run an Anchor client in Python. For the handful of instructions the
backend needs to build, computing the 8-byte discriminator and Borsh-encoding
the arguments by hand is less machinery than a code generator, and it keeps the
dependency list short.

Anchor's rule: the instruction discriminator is the first 8 bytes of
sha256("global:<snake_case_instruction_name>"). Account discriminators use the
"account:<PascalCaseName>" prefix instead.
"""

from __future__ import annotations

import hashlib
import struct


def instruction_discriminator(name: str) -> bytes:
    """8-byte discriminator Anchor prepends to instruction data."""
    return hashlib.sha256(f"global:{name}".encode()).digest()[:8]


def account_discriminator(name: str) -> bytes:
    """8-byte discriminator Anchor prepends to account data."""
    return hashlib.sha256(f"account:{name}".encode()).digest()[:8]


def encode_u64(value: int) -> bytes:
    if not 0 <= value < 2**64:
        raise ValueError(f"u64 out of range: {value}")
    return struct.pack("<Q", value)


def decode_u64(data: bytes, offset: int = 0) -> int:
    return int(struct.unpack_from("<Q", data, offset)[0])


def encode_string(value: str) -> bytes:
    """Borsh string: u32 little-endian byte length, then UTF-8 bytes."""
    raw = value.encode()
    return struct.pack("<I", len(raw)) + raw
