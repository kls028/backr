from __future__ import annotations

import base64

import pytest
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction import VersionedTransaction

from app.solana.campaign import (
    CampaignInitializationArgs,
    build_initialize_campaign_ix,
    build_purchase_subscription_ix,
    build_settle_position_ix,
    campaign_pda,
    decode_initialize_campaign_data,
    position_pda,
)
from app.solana.tx import to_unsigned_transaction

PROGRAM = Pubkey.from_string("5dzttAFNMi3JNtBcBQzJWcyXwou4rN2z6KX5DitDSDHe")
CREATOR = Pubkey.from_string("7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU")
USDC_MINT = Pubkey.from_string("So11111111111111111111111111111111111111112")
BLOCKHASH = "11111111111111111111111111111111"


def valid_args() -> CampaignInitializationArgs:
    return CampaignInitializationArgs(
        nonce=b"0123456789abcdef",
        unit_price_atomic=25_000_000,
        minimum_success_threshold_atomic=800_000_000,
        main_goal_atomic=1_000_000_000,
        stretch_goals_atomic=[1_250_000_000, 1_500_000_000],
        start_at=1_790_000_000,
        end_at=1_800_000_000,
        metadata_uri="https://example.invalid/campaign.json",
        metadata_hash=bytes(range(32)),
    )


def test_campaign_pda_uses_creator_and_nonce() -> None:
    address, bump = campaign_pda(PROGRAM, CREATOR, valid_args().nonce)
    assert not address.is_on_curve()
    assert 0 <= bump <= 255


def test_campaign_instruction_uses_expected_accounts() -> None:
    ix = build_initialize_campaign_ix(
        PROGRAM, CREATOR, USDC_MINT, Pubkey.new_unique(), valid_args()
    )
    campaign, _ = campaign_pda(PROGRAM, CREATOR, valid_args().nonce)
    assert ix.program_id == PROGRAM
    assert [meta.pubkey for meta in ix.accounts][:3] == [CREATOR, campaign, USDC_MINT]
    assert ix.accounts[0].is_signer is True
    assert ix.accounts[1].is_writable is True


def test_campaign_transaction_has_no_backend_signature() -> None:
    transaction = to_unsigned_transaction(
        [
            build_initialize_campaign_ix(
                PROGRAM, CREATOR, USDC_MINT, Pubkey.new_unique(), valid_args()
            )
        ],
        CREATOR,
        BLOCKHASH,
    )
    decoded = VersionedTransaction.from_bytes(base64.b64decode(transaction))
    assert decoded.signatures[0] == Signature.default()


def test_campaign_instruction_data_round_trips_with_anchor_layout() -> None:
    args = valid_args()
    instruction = build_initialize_campaign_ix(
        PROGRAM, CREATOR, USDC_MINT, Pubkey.new_unique(), args
    )
    assert decode_initialize_campaign_data(instruction.data) == args


def test_position_pda_and_purchase_instruction_use_expected_accounts() -> None:
    """Account order must mirror `PurchaseSubscription` in campaign.rs exactly —
    Anchor resolves positionally, so a swap here fails on-chain with an opaque
    constraint error."""
    supporter = Pubkey.new_unique()
    campaign = Pubkey.new_unique()
    source = Pubkey.new_unique()
    escrow = Pubkey.new_unique()
    athlete_token = Pubkey.new_unique()
    position, _ = position_pda(PROGRAM, campaign, supporter)
    ix = build_purchase_subscription_ix(
        PROGRAM,
        campaign,
        supporter,
        source,
        escrow,
        athlete_token,
        USDC_MINT,
        2,
    )

    assert [meta.pubkey for meta in ix.accounts[:7]] == [
        campaign,
        position,
        supporter,
        source,
        escrow,
        athlete_token,
        USDC_MINT,
    ]
    assert ix.accounts[2].is_signer
    # The athlete's account receives the non-refundable immediate unit, so it
    # must be writable.
    assert ix.accounts[5].is_writable


def test_settlement_instruction_is_permissionless_with_both_destinations() -> None:
    """Settlement may be cranked by anyone; the on-chain constraints — not the
    signer — are what protect the payout destinations."""
    campaign = Pubkey.new_unique()
    cranker = Pubkey.new_unique()
    supporter_token = Pubkey.new_unique()
    athlete_token = Pubkey.new_unique()
    escrow = Pubkey.new_unique()
    ix = build_settle_position_ix(
        PROGRAM,
        campaign,
        CREATOR,
        cranker,
        supporter_token,
        athlete_token,
        escrow,
        USDC_MINT,
        True,
    )

    assert ix.accounts[2].pubkey == cranker
    assert ix.accounts[2].is_signer
    # Refund destination and payout destination, in that order.
    assert ix.accounts[3].pubkey == supporter_token
    assert ix.accounts[4].pubkey == athlete_token
    assert ix.accounts[5].pubkey == escrow


def test_settlement_rejects_a_default_cranker() -> None:
    with pytest.raises(ValueError):
        build_settle_position_ix(
            PROGRAM,
            Pubkey.new_unique(),
            CREATOR,
            Pubkey.default(),
            Pubkey.new_unique(),
            Pubkey.new_unique(),
            Pubkey.new_unique(),
            USDC_MINT,
            False,
        )
