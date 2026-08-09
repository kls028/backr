from __future__ import annotations

import base64

from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction import VersionedTransaction

from app.solana.campaign import (
    CampaignInitializationArgs,
    build_initialize_campaign_ix,
    build_purchase_subscription_ix,
    build_settle_position_ix,
    campaign_pda,
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


def test_position_pda_and_purchase_instruction_use_expected_accounts() -> None:
    supporter = Pubkey.new_unique()
    campaign = Pubkey.new_unique()
    position, _ = position_pda(PROGRAM, campaign, supporter)
    ix = build_purchase_subscription_ix(
        PROGRAM,
        campaign,
        supporter,
        Pubkey.new_unique(),
        Pubkey.new_unique(),
        USDC_MINT,
        2,
    )

    assert ix.accounts[0].pubkey == campaign
    assert ix.accounts[1].pubkey == position
    assert ix.accounts[2].is_signer


def test_settlement_instruction_marks_creator_as_signer() -> None:
    campaign = Pubkey.new_unique()
    ix = build_settle_position_ix(
        PROGRAM,
        campaign,
        CREATOR,
        CREATOR,
        Pubkey.new_unique(),
        Pubkey.new_unique(),
        USDC_MINT,
        True,
    )

    assert ix.accounts[2].pubkey == CREATOR
    assert ix.accounts[2].is_signer
