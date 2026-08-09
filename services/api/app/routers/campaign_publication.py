"""Unsigned campaign publication and chain-confirmation intent handling."""

from __future__ import annotations

import datetime as dt
import secrets
import uuid
from typing import TypedDict

from fastapi import APIRouter, HTTPException, status
from solders.pubkey import Pubkey
from solders.signature import Signature
from sqlalchemy import select

from app.auth import CurrentUserDep
from app.db import SessionDep, SettingsDep
from app.domain.campaigns import (
    campaign_snapshot_hash,
    canonical_campaign_snapshot,
)
from app.models import Profile
from app.platform_models import (
    Campaign,
    CampaignPublishIntent,
    CampaignRewardTier,
    CampaignStretchGoal,
)
from app.routers.plans import _athlete
from app.routers.transactions import RpcDep, _compile
from app.schemas.campaigns import (
    CampaignPublishConfirm,
    CampaignPublishConfirmOut,
    CampaignPublishOut,
    CampaignPublishRequest,
    SettlementIntentOut,
    SettlementRequest,
)
from app.solana.campaign import (
    CampaignInitializationArgs,
    build_initialize_campaign_ix,
    build_settle_position_ix,
    campaign_pda,
)
from app.solana.client import RpcError

router = APIRouter(prefix="/athlete/campaigns", tags=["campaign-publication"])


class CampaignTerms(TypedDict):
    unit_price_atomic: int
    minimum_success_threshold_atomic: int
    main_goal_atomic: int
    stretch_goals_atomic: list[int]
    start_at: dt.datetime
    end_at: dt.datetime
    metadata_uri: str
    escrow_token_account: str
    reward_tiers: list[dict[str, object]]


async def _load_terms(session: SessionDep, campaign: Campaign) -> CampaignTerms:
    goals = list(
        await session.scalars(
            select(CampaignStretchGoal)
            .where(CampaignStretchGoal.campaign_id == campaign.id)
            .order_by(CampaignStretchGoal.position)
        )
    )
    tiers = list(
        await session.scalars(
            select(CampaignRewardTier)
            .where(CampaignRewardTier.campaign_id == campaign.id)
            .order_by(CampaignRewardTier.position)
        )
    )
    return {
        "unit_price_atomic": campaign.unit_price_atomic,
        "minimum_success_threshold_atomic": campaign.minimum_success_threshold_atomic,
        "main_goal_atomic": campaign.main_goal_atomic or campaign.minimum_success_threshold_atomic,
        "stretch_goals_atomic": [goal.amount_atomic for goal in goals],
        "start_at": campaign.start_at,
        "end_at": campaign.end_at,
        "metadata_uri": campaign.metadata_uri or "",
        "escrow_token_account": campaign.escrow_token_account or "",
        "reward_tiers": [
            {
                "required_units": tier.required_units,
                "benefit": tier.benefit,
                "is_cumulative": tier.is_cumulative,
                "max_supply": tier.max_supply,
                "max_per_supporter": tier.max_per_supporter,
                "uri": tier.uri,
            }
            for tier in tiers
        ],
    }


def _publish_out(intent: CampaignPublishIntent) -> CampaignPublishOut:
    return CampaignPublishOut(
        campaign_id=intent.campaign_id,
        publish_intent_id=intent.id,
        campaign_pda=intent.campaign_pda,
        snapshot_hash=intent.snapshot_hash.hex(),
        transaction=intent.unsigned_transaction,
        blockhash=intent.blockhash,
        last_valid_block_height=intent.last_valid_block_height,
        simulation_logs=[str(item) for item in intent.simulation_logs],
    )


@router.post("/{campaign_id}/publish", response_model=CampaignPublishOut)
async def publish_campaign(
    campaign_id: uuid.UUID,
    payload: CampaignPublishRequest,
    user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
    rpc: RpcDep,
) -> CampaignPublishOut:
    athlete = await _athlete(user, session)
    campaign = await session.scalar(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.athlete_profile_id == athlete.id,
        )
    )
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    existing = await session.scalar(
        select(CampaignPublishIntent).where(CampaignPublishIntent.campaign_id == campaign.id)
    )
    if existing is not None:
        return _publish_out(existing)
    if campaign.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Campaign is not a draft")
    if not settings.usdc_mint:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="USDC mint is not configured"
        )

    try:
        creator = Pubkey.from_string(user.wallet or "")
        program_id = Pubkey.from_string(settings.program_id)
        usdc_mint = Pubkey.from_string(settings.usdc_mint)
        escrow_token_account = Pubkey.from_string(payload.escrow_token_account)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Solana configuration is invalid",
        ) from exc

    nonce = secrets.token_bytes(16)
    terms = await _load_terms(session, campaign)
    terms["escrow_token_account"] = str(escrow_token_account)
    snapshot = canonical_campaign_snapshot(terms, campaign.id, nonce)
    snapshot_hash = campaign_snapshot_hash(snapshot)
    args = CampaignInitializationArgs(
        nonce=nonce,
        unit_price_atomic=int(terms["unit_price_atomic"]),
        minimum_success_threshold_atomic=int(terms["minimum_success_threshold_atomic"]),
        main_goal_atomic=int(terms["main_goal_atomic"]),
        stretch_goals_atomic=[int(item) for item in terms["stretch_goals_atomic"]],
        start_at=int(campaign.start_at.timestamp()),
        end_at=int(campaign.end_at.timestamp()),
        metadata_uri=str(terms["metadata_uri"]),
        metadata_hash=snapshot_hash,
    )
    pda, _ = campaign_pda(program_id, creator, nonce)
    unsigned = await _compile(
        rpc,
        settings,
        [build_initialize_campaign_ix(program_id, creator, usdc_mint, escrow_token_account, args)],
        creator,
    )
    intent = CampaignPublishIntent(
        campaign_id=campaign.id,
        campaign_pda=str(pda),
        nonce=nonce,
        snapshot_hash=snapshot_hash,
        unsigned_transaction=unsigned.transaction,
        blockhash=unsigned.blockhash,
        last_valid_block_height=unsigned.last_valid_block_height,
        simulation_logs=unsigned.simulation_logs,
    )
    campaign.nonce = nonce
    campaign.metadata_hash = snapshot_hash
    campaign.publish_snapshot = {"snapshot": snapshot.decode("utf-8"), "nonce": nonce.hex()}
    campaign.campaign_pda = str(pda)
    campaign.escrow_token_account = str(escrow_token_account)
    session.add(intent)
    await session.flush()
    return _publish_out(intent)


@router.post("/{campaign_id}/publish/confirm", response_model=CampaignPublishConfirmOut)
async def confirm_campaign_publish(
    campaign_id: uuid.UUID,
    payload: CampaignPublishConfirm,
    user: CurrentUserDep,
    session: SessionDep,
    rpc: RpcDep,
    settings: SettingsDep,
) -> CampaignPublishConfirmOut:
    athlete = await _athlete(user, session)
    campaign = await session.scalar(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.athlete_profile_id == athlete.id,
        )
    )
    intent = await session.scalar(
        select(CampaignPublishIntent).where(CampaignPublishIntent.campaign_id == campaign_id)
    )
    if campaign is None or intent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Publish intent not found"
        )
    if payload.campaign_pda != intent.campaign_pda:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Campaign PDA does not match intent"
        )
    try:
        Signature.from_string(payload.signature)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Malformed transaction signature",
        ) from exc
    try:
        transaction = await rpc.get_transaction(payload.signature)
    except RpcError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unable to verify publication: {exc.rpc_message}",
        ) from exc
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Publication signature is not confirmed",
        )
    if (transaction.get("meta") or {}).get("err") is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Publication transaction failed on-chain",
        )
    message = (transaction.get("transaction") or {}).get("message") or {}
    account_keys = message.get("accountKeys") or []
    account_key_strings = {
        key if isinstance(key, str) else str(key.get("pubkey", ""))
        for key in account_keys
        if isinstance(key, str) or isinstance(key, dict)
    }
    if not {
        intent.campaign_pda,
        user.wallet or "",
        settings.program_id,
    }.issubset(account_key_strings):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Publication signature does not match the campaign intent",
        )
    now = dt.datetime.now(tz=dt.UTC)
    if intent.confirmation_signature and intent.confirmation_signature != payload.signature:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Campaign already has a different signature",
        )
    intent.confirmation_signature = payload.signature
    intent.confirmed_at = now
    campaign.chain_signature = payload.signature
    campaign.status = "scheduled"
    await session.flush()
    return CampaignPublishConfirmOut(
        campaign_id=campaign.id,
        publish_intent_id=intent.id,
        signature=payload.signature,
        status=campaign.status,
        confirmed_at=now,
    )


@router.post("/{campaign_id}/settle", response_model=SettlementIntentOut)
async def settle_campaign_position(
    campaign_id: uuid.UUID,
    payload: SettlementRequest,
    user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
    rpc: RpcDep,
) -> SettlementIntentOut:
    athlete = await _athlete(user, session)
    campaign = await session.scalar(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.athlete_profile_id == athlete.id,
        )
    )
    creator_profile = await session.get(Profile, user.id)
    if campaign is None or creator_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if not campaign.campaign_pda or not settings.usdc_mint:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Campaign escrow is not configured",
        )
    try:
        program_id = Pubkey.from_string(settings.program_id)
        campaign_address = Pubkey.from_string(campaign.campaign_pda)
        creator = Pubkey.from_string(creator_profile.wallet or "")
        supporter = Pubkey.from_string(payload.supporter_wallet)
        supporter_token = Pubkey.from_string(payload.supporter_token_account)
        escrow_token = Pubkey.from_string(payload.escrow_token_account)
        usdc_mint = Pubkey.from_string(settings.usdc_mint)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Settlement contains a malformed Solana address",
        ) from exc
    unsigned = await _compile(
        rpc,
        settings,
        [
            build_settle_position_ix(
                program_id,
                campaign_address,
                supporter,
                creator,
                supporter_token,
                escrow_token,
                usdc_mint,
                payload.successful,
            )
        ],
        creator,
    )
    return SettlementIntentOut(
        campaign_id=campaign.id,
        successful=payload.successful,
        transaction=unsigned.transaction,
        blockhash=unsigned.blockhash,
        last_valid_block_height=unsigned.last_valid_block_height,
        simulation_logs=unsigned.simulation_logs,
    )
