from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from solders.pubkey import Pubkey

from app.indexer.parser import (
    IndexerParseError,
    parse_campaign_initialization,
    verify_campaign_publish,
)
from app.platform_models import Campaign, CampaignPublishIntent
from app.solana.campaign import CampaignInitializationArgs, build_initialize_campaign_ix

PROGRAM = Pubkey.from_string("5dzttAFNMi3JNtBcBQzJWcyXwou4rN2z6KX5DitDSDHe")
CREATOR = Pubkey.from_string("7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU")
USDC_MINT = Pubkey.from_string("So11111111111111111111111111111111111111112")


def _base58_encode(data: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = int.from_bytes(data, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded
    return "1" * (len(data) - len(data.lstrip(b"\0"))) + (encoded or "")


def _args() -> CampaignInitializationArgs:
    return CampaignInitializationArgs(
        nonce=b"0123456789abcdef",
        unit_price_atomic=25_000_000,
        minimum_success_threshold_atomic=800_000_000,
        main_goal_atomic=1_000_000_000,
        stretch_goals_atomic=[1_250_000_000],
        start_at=1_790_000_000,
        end_at=1_800_000_000,
        metadata_uri="https://example.invalid/campaign.json",
        metadata_hash=bytes(range(32)),
    )


def _transaction(program_id: Pubkey = PROGRAM) -> dict[str, object]:
    escrow = Pubkey.new_unique()
    instruction = build_initialize_campaign_ix(program_id, CREATOR, USDC_MINT, escrow, _args())
    keys = [
        CREATOR,
        instruction.accounts[1].pubkey,
        USDC_MINT,
        escrow,
        instruction.accounts[4].pubkey,
    ]
    return {
        "signature": "publication-signature",
        "meta": {"err": None},
        "transaction": {
            "message": {
                "accountKeys": [
                    {"pubkey": str(key), "signer": index == 0} for index, key in enumerate(keys)
                ],
                "instructions": [
                    {
                        "programId": str(program_id),
                        "accounts": [str(key) for key in keys],
                        "data": _base58_encode(bytes(instruction.data)),
                    }
                ],
            }
        },
    }


def test_parser_rejects_a_creator_that_did_not_sign() -> None:
    entry = _transaction()
    entry["transaction"]["message"]["accountKeys"][0]["signer"] = False  # type: ignore[index]
    with pytest.raises(IndexerParseError, match="creator signer"):
        parse_campaign_initialization(entry, str(PROGRAM))


def test_parser_extracts_and_validates_campaign_initialization() -> None:
    parsed = parse_campaign_initialization(_transaction(), str(PROGRAM))
    assert parsed.creator == str(CREATOR)
    assert parsed.usdc_mint == str(USDC_MINT)
    assert parsed.unit_price_atomic == 25_000_000
    assert parsed.metadata_hash == bytes(range(32))


def test_parser_rejects_an_unexpected_program() -> None:
    with pytest.raises(IndexerParseError, match="unexpected program"):
        parse_campaign_initialization(_transaction(Pubkey.new_unique()), str(PROGRAM))


def test_parser_rejects_a_campaign_pda_that_does_not_match_the_nonce() -> None:
    entry = _transaction()
    instruction = entry["transaction"]["message"]["instructions"][0]  # type: ignore[index]
    instruction["accounts"][1] = str(Pubkey.new_unique())  # type: ignore[index]
    with pytest.raises(IndexerParseError, match="campaign PDA"):
        parse_campaign_initialization(entry, str(PROGRAM))


def test_publish_verification_compares_snapshot_terms_and_pending_signature() -> None:
    args = _args()
    entry = _transaction()
    parsed = parse_campaign_initialization(entry, str(PROGRAM))
    campaign_id = uuid.uuid4()
    snapshot = {
        "campaign_id": str(campaign_id),
        "nonce": args.nonce.hex(),
        "terms": {
            "unit_price_atomic": args.unit_price_atomic,
            "minimum_success_threshold_atomic": args.minimum_success_threshold_atomic,
            "main_goal_atomic": args.main_goal_atomic,
            "stretch_goals_atomic": args.stretch_goals_atomic,
            "start_at": datetime.fromtimestamp(args.start_at, tz=UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "end_at": datetime.fromtimestamp(args.end_at, tz=UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "metadata_uri": args.metadata_uri,
            "escrow_token_account": parsed.escrow_token_account,
            "reward_tiers": [],
        },
    }
    intent = CampaignPublishIntent(
        campaign_id=campaign_id,
        campaign_pda=parsed.campaign_pda,
        nonce=args.nonce,
        snapshot_hash=args.metadata_hash,
        unsigned_transaction="unsigned",
        blockhash="blockhash",
        last_valid_block_height=1,
        confirmation_signature="publication-signature",
    )
    campaign = Campaign(id=campaign_id, publish_snapshot={"snapshot": json.dumps(snapshot)})

    verify_campaign_publish(intent, campaign, parsed, str(USDC_MINT))


def test_publish_verification_rejects_a_different_signature() -> None:
    parsed = parse_campaign_initialization(_transaction(), str(PROGRAM))
    intent = CampaignPublishIntent(
        campaign_pda=parsed.campaign_pda,
        nonce=_args().nonce,
        snapshot_hash=_args().metadata_hash,
        confirmation_signature="different-signature",
    )
    with pytest.raises(IndexerParseError, match="signature"):
        verify_campaign_publish(intent, Campaign(), parsed, str(USDC_MINT))
