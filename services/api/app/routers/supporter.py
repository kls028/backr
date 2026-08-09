"""Supporter purchase intents and Support Point read models."""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, HTTPException, status
from solders.pubkey import Pubkey
from sqlalchemy import select

from app.auth import CurrentUserDep
from app.db import SessionDep, SettingsDep
from app.domain.settlement import allocate_purchase
from app.platform_models import (
    Campaign,
    Contribution,
    Subscription,
    SupportPointAccount,
    SupportPointLedger,
)
from app.routers.transactions import RpcDep, _compile
from app.schemas.supporter import (
    ContributionOut,
    PurchaseIntentOut,
    PurchaseRequest,
    SupportPointAccountOut,
    SupportPointLedgerOut,
)
from app.solana.campaign import build_purchase_subscription_ix

router = APIRouter(tags=["supporter"])


def _wallet(value: str | None) -> Pubkey:
    if not value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Wallet address required"
        )
    try:
        return Pubkey.from_string(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed wallet address"
        ) from exc


@router.post(
    "/campaigns/{campaign_id}/purchase",
    response_model=PurchaseIntentOut,
)
async def purchase_campaign(
    campaign_id: uuid.UUID,
    payload: PurchaseRequest,
    user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
    rpc: RpcDep,
) -> PurchaseIntentOut:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    now = dt.datetime.now(tz=dt.UTC)
    if (
        campaign.status not in ("scheduled", "active", "funded")
        or not campaign.start_at <= now < campaign.end_at
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Campaign is not accepting purchases"
        )
    if not campaign.campaign_pda or not settings.usdc_mint:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Campaign escrow is not configured",
        )

    wallet = _wallet(user.wallet)
    try:
        campaign_address = Pubkey.from_string(campaign.campaign_pda)
        usdc_mint = Pubkey.from_string(settings.usdc_mint)
        source = Pubkey.from_string(payload.source_token_account)
        escrow = Pubkey.from_string(payload.escrow_token_account)
        program_id = Pubkey.from_string(settings.program_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Solana configuration is invalid",
        ) from exc
    if campaign.escrow_token_account != str(escrow):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Escrow token account does not match the published campaign",
        )

    active_units = (
        await session.scalar(
            select(Subscription.active_units).where(
                Subscription.supporter_profile_id == user.id,
                Subscription.athlete_profile_id == campaign.athlete_profile_id,
                Subscription.campaign_id == campaign.id,
            )
        )
        or 0
    )
    allocation = allocate_purchase(payload.purchased_units, int(active_units))
    unsigned = await _compile(
        rpc,
        settings,
        [
            build_purchase_subscription_ix(
                program_id,
                campaign_address,
                wallet,
                source,
                escrow,
                usdc_mint,
                payload.purchased_units,
            )
        ],
        wallet,
    )
    if campaign.status == "scheduled":
        campaign.status = "active"
        await session.flush()
    return PurchaseIntentOut(
        campaign_id=campaign.id,
        purchased_units=payload.purchased_units,
        amount_atomic=campaign.unit_price_atomic * payload.purchased_units,
        immediate_units=allocation.immediate_units,
        pending_units=allocation.pending_units,
        confirmed_points=allocation.confirmed_points,
        pending_points=allocation.pending_points,
        transaction=unsigned.transaction,
        blockhash=unsigned.blockhash,
        last_valid_block_height=unsigned.last_valid_block_height,
        simulation_logs=unsigned.simulation_logs,
    )


@router.get("/supporter/points", response_model=SupportPointAccountOut)
async def read_points(user: CurrentUserDep, session: SessionDep) -> SupportPointAccountOut:
    account = await session.get(SupportPointAccount, user.id)
    now = dt.datetime.now(tz=dt.UTC)
    return SupportPointAccountOut(
        profile_id=user.id,
        available_points=account.available_points if account else 0,
        pending_points=account.pending_points if account else 0,
        updated_at=account.updated_at if account and account.updated_at else now,
    )


@router.get("/supporter/points/ledger", response_model=list[SupportPointLedgerOut])
async def read_point_ledger(
    user: CurrentUserDep, session: SessionDep, limit: int = 50
) -> list[SupportPointLedgerOut]:
    rows = list(
        await session.scalars(
            select(SupportPointLedger)
            .where(SupportPointLedger.profile_id == user.id)
            .order_by(SupportPointLedger.created_at.desc(), SupportPointLedger.id.desc())
            .limit(min(max(limit, 1), 100))
        )
    )
    return [SupportPointLedgerOut.model_validate(row) for row in rows]


@router.get("/supporter/contributions", response_model=list[ContributionOut])
async def read_contributions(
    user: CurrentUserDep, session: SessionDep, limit: int = 50
) -> list[ContributionOut]:
    rows = list(
        await session.scalars(
            select(Contribution)
            .where(Contribution.supporter_profile_id == user.id)
            .order_by(Contribution.created_at.desc(), Contribution.id.desc())
            .limit(min(max(limit, 1), 100))
        )
    )
    return [ContributionOut.model_validate(row) for row in rows]
