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

from solders.pubkey import Pubkey

MONTHLY_SUB_SEED = b"subsplan"

def plan_pda(program_id: Pubkey, creator: Pubkey) -> tuple[Pubkey, int]:
    """Matches seeds = [MONTHLY_SUB_SEED, creator.key().as_ref()]"""
    return Pubkey.find_program_address([MONTHLY_SUB_SEED, bytes(creator)], program_id)


def subscription_pda(program_id: Pubkey, plan: Pubkey, supporter: Pubkey) -> tuple[Pubkey, int]:
    """Matches seeds = [b"supporter_sub", plan.key().as_ref(), supporter.key().as_ref()]"""
    return Pubkey.find_program_address(
        [MONTHLY_SUB_SEED, bytes(plan), bytes(supporter)], program_id
    )

def encode_create_subscription_plan_data(price: int, usdc_mint: Pubkey) -> bytes:
    """Encodes price (u64) and usdc_mint (Pubkey)"""
    data = bytearray(instruction_discriminator("create_subscription_plan"))
    data.extend(struct.pack("<Q", price)) # <Q is unsigned 64-bit integer, little-endian
    data.extend(bytes(usdc_mint))         # Pubkey serializes to 32 bytes
    return bytes(data)


def encode_purchase_subscription_plan_data(months: int) -> bytes:
    """Encodes months (u64)"""
    data = bytearray(instruction_discriminator("handle_purchase_subscription_plan"))
    data.extend(struct.pack("<Q", months))
    return bytes(data)

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
