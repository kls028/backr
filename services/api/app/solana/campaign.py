"""Anchor campaign initialization encoding."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from solders.instruction import AccountMeta, Instruction
from solders.pubkey import Pubkey
from solders.system_program import ID as SYSTEM_PROGRAM_ID

from app.solana.anchor import (
    TOKEN_PROGRAM_ID,
    encode_string,
    encode_u64,
    instruction_discriminator,
)

CAMPAIGN_SEED = b"campaign"
POSITION_SEED = b"position"

__all__ = ["CAMPAIGN_SEED", "POSITION_SEED", "TOKEN_PROGRAM_ID"]


@dataclass(frozen=True, slots=True)
class CampaignInitializationArgs:
    nonce: bytes
    unit_price_atomic: int
    minimum_success_threshold_atomic: int
    main_goal_atomic: int
    stretch_goals_atomic: list[int]
    start_at: int
    end_at: int
    metadata_uri: str
    metadata_hash: bytes


def campaign_pda(program_id: Pubkey, creator: Pubkey, nonce: bytes) -> tuple[Pubkey, int]:
    if len(nonce) != 16:
        raise ValueError("campaign nonce must be exactly 16 bytes")
    return Pubkey.find_program_address([CAMPAIGN_SEED, bytes(creator), nonce], program_id)


def position_pda(program_id: Pubkey, campaign: Pubkey, supporter: Pubkey) -> tuple[Pubkey, int]:
    return Pubkey.find_program_address(
        [POSITION_SEED, bytes(campaign), bytes(supporter)], program_id
    )


def _encode_i64(value: int) -> bytes:
    return struct.pack("<q", value)


def _encode_args(args: CampaignInitializationArgs) -> bytes:
    if len(args.metadata_hash) != 32:
        raise ValueError("metadata hash must be exactly 32 bytes")
    if len(args.nonce) != 16:
        raise ValueError("campaign nonce must be exactly 16 bytes")
    if len(args.stretch_goals_atomic) > 8:
        raise ValueError("campaign supports at most 8 stretch goals")
    data = bytearray(instruction_discriminator("initialize_campaign"))
    data.extend(args.nonce)
    data.extend(encode_u64(args.unit_price_atomic))
    data.extend(encode_u64(args.minimum_success_threshold_atomic))
    data.extend(encode_u64(args.main_goal_atomic))
    data.extend(struct.pack("<I", len(args.stretch_goals_atomic)))
    for goal in args.stretch_goals_atomic:
        data.extend(encode_u64(goal))
    data.extend(_encode_i64(args.start_at))
    data.extend(_encode_i64(args.end_at))
    data.extend(encode_string(args.metadata_uri))
    data.extend(args.metadata_hash)
    return bytes(data)


def encode_initialize_campaign_data(args: CampaignInitializationArgs) -> bytes:
    """Encode the exact Anchor instruction payload for indexer comparisons."""
    return _encode_args(args)


def decode_initialize_campaign_data(data: bytes) -> CampaignInitializationArgs:
    """Decode and strictly validate an initialize-campaign instruction payload."""
    discriminator = instruction_discriminator("initialize_campaign")
    if not data.startswith(discriminator):
        raise ValueError("unexpected initialize_campaign discriminator")
    offset = len(discriminator)

    def take(size: int) -> bytes:
        nonlocal offset
        if offset + size > len(data):
            raise ValueError("truncated initialize_campaign instruction")
        value = data[offset : offset + size]
        offset += size
        return value

    nonce = take(16)
    unit_price_atomic = struct.unpack("<Q", take(8))[0]
    minimum_success_threshold_atomic = struct.unpack("<Q", take(8))[0]
    main_goal_atomic = struct.unpack("<Q", take(8))[0]
    stretch_count = struct.unpack("<I", take(4))[0]
    if stretch_count > 8:
        raise ValueError("too many stretch goals in instruction")
    stretch_goals_atomic = [struct.unpack("<Q", take(8))[0] for _ in range(stretch_count)]
    start_at = struct.unpack("<q", take(8))[0]
    end_at = struct.unpack("<q", take(8))[0]
    metadata_length = struct.unpack("<I", take(4))[0]
    metadata_uri = take(metadata_length).decode("utf-8")
    metadata_hash = take(32)
    if offset != len(data):
        raise ValueError("unexpected trailing initialize_campaign data")
    return CampaignInitializationArgs(
        nonce=nonce,
        unit_price_atomic=unit_price_atomic,
        minimum_success_threshold_atomic=minimum_success_threshold_atomic,
        main_goal_atomic=main_goal_atomic,
        stretch_goals_atomic=stretch_goals_atomic,
        start_at=start_at,
        end_at=end_at,
        metadata_uri=metadata_uri,
        metadata_hash=metadata_hash,
    )


def build_initialize_campaign_ix(
    program_id: Pubkey,
    creator: Pubkey,
    usdc_mint: Pubkey,
    escrow_token_account: Pubkey,
    args: CampaignInitializationArgs,
) -> Instruction:
    campaign, _ = campaign_pda(program_id, creator, args.nonce)
    return Instruction(
        program_id=program_id,
        accounts=[
            AccountMeta(pubkey=creator, is_signer=True, is_writable=True),
            AccountMeta(pubkey=campaign, is_signer=False, is_writable=True),
            AccountMeta(pubkey=usdc_mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=escrow_token_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
        ],
        data=_encode_args(args),
    )


def build_purchase_subscription_ix(
    program_id: Pubkey,
    campaign: Pubkey,
    supporter: Pubkey,
    source_token_account: Pubkey,
    escrow_token_account: Pubkey,
    athlete_token_account: Pubkey,
    usdc_mint: Pubkey,
    purchased_units: int,
) -> Instruction:
    """Build the wallet-signed checked SPL-token purchase instruction.

    Account order must match `#[derive(Accounts)] pub struct PurchaseSubscription`
    exactly -- Anchor resolves positionally. `athlete_token_account` receives the
    non-refundable immediate unit; only the pending units go to escrow.
    """
    if purchased_units <= 0:
        raise ValueError("purchased_units must be positive")
    position, _ = position_pda(program_id, campaign, supporter)
    data = bytearray(instruction_discriminator("purchase_subscription"))
    data.extend(encode_u64(purchased_units))
    return Instruction(
        program_id=program_id,
        accounts=[
            AccountMeta(pubkey=campaign, is_signer=False, is_writable=True),
            AccountMeta(pubkey=position, is_signer=False, is_writable=True),
            AccountMeta(pubkey=supporter, is_signer=True, is_writable=True),
            AccountMeta(pubkey=source_token_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=escrow_token_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=athlete_token_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=usdc_mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
            AccountMeta(pubkey=SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
        ],
        data=bytes(data),
    )


def build_settle_position_ix(
    program_id: Pubkey,
    campaign: Pubkey,
    supporter: Pubkey,
    cranker: Pubkey,
    supporter_token_account: Pubkey,
    athlete_token_account: Pubkey,
    escrow_token_account: Pubkey,
    usdc_mint: Pubkey,
    successful: bool,
) -> Instruction:
    """Build a settlement instruction for one supporter position.

    Settlement is permissionless: `cranker` only pays the fee and signs. Every
    payout destination is constrained on-chain against campaign/position state,
    so a hostile cranker cannot redirect funds. Previously this required the
    athlete's signature, which meant an absent athlete could strand refunds.
    """
    if cranker == Pubkey.default():
        raise ValueError("cranker must be a valid fee payer")
    position, _ = position_pda(program_id, campaign, supporter)
    data = bytearray(instruction_discriminator("settle_position"))
    data.append(1 if successful else 0)
    return Instruction(
        program_id=program_id,
        accounts=[
            AccountMeta(pubkey=campaign, is_signer=False, is_writable=True),
            AccountMeta(pubkey=position, is_signer=False, is_writable=True),
            AccountMeta(pubkey=cranker, is_signer=True, is_writable=True),
            AccountMeta(pubkey=supporter_token_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=athlete_token_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=escrow_token_account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=usdc_mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        ],
        data=bytes(data),
    )
