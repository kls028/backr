"""Subscription-plan authoring for athlete accounts."""

from __future__ import annotations

import datetime as dt
import os
import uuid

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from solders.pubkey import Pubkey
from sqlalchemy import select

from app.auth import CurrentUserDep
from app.db import SessionDep
from app.domain.money import format_usdc_amount, parse_usdc_amount
from app.models import Profile
from app.platform_models import AthleteProfile, Campaign, CampaignPublishIntent, SubscriptionPlan
from app.schemas.plans import SubscriptionPlanCreate, SubscriptionPlanOut, SubscriptionPlanUpdate
from app.solana.anchor import plan_pda
from app.solana.client import SolanaRpc
from app.solana.tx import (
    build_create_subscription_plan_ix,
    build_purchase_subscription_plan_ix,
    to_unsigned_transaction,
)

router = APIRouter(prefix="/subscription-plans", tags=["subscription-plans"])

# Load the environment variables from .env
load_dotenv()

# Fetch the strings from the environment, falling back to safe defaults if needed
PROGRAM_ID_STR = os.getenv("PROGRAM_ID", "11111111111111111111111111111111")
USDC_MINT_STR = os.getenv("USDC_MINT", "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU")
RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.devnet.solana.com")

# Convert them to Pubkey objects once at startup
PROGRAM_ID = Pubkey.from_string(PROGRAM_ID_STR)
USDC_MINT = Pubkey.from_string(USDC_MINT_STR)

def _wallet(value: str | None) -> str:
    """Reject a transaction build when the wallet claim is missing."""
    if not value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Wallet address unavailable"
        )
    return value


class TransactionResponse(BaseModel):
    transaction_b64: str

@router.post("/{plan_id}/transaction/create", response_model=TransactionResponse)
async def get_create_plan_transaction(
    plan_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> TransactionResponse:
    """Generates the unsigned transaction for an athlete to initialize their plan on-chain."""
    
    athlete = await _athlete(user, session)
    plan = await session.scalar(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == plan_id,
            SubscriptionPlan.athlete_profile_id == athlete.id,
        )
    )
    
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    creator_pubkey = Pubkey.from_string(_wallet(user.wallet))

    # 1. Build the instruction using the imported function
    ix = build_create_subscription_plan_ix(
        program_id=PROGRAM_ID,
        creator=creator_pubkey,
        usdc_mint=USDC_MINT,
        price=plan.unit_price_atomic
    )

    # 2. Fetch the latest blockhash from the Solana RPC
    async with SolanaRpc(RPC_URL) as rpc:
        blockhash, _ = await rpc.get_latest_blockhash()

    # 3. Compile the base64 transaction string to send to the frontend
    unsigned_tx_b64 = to_unsigned_transaction([ix], creator_pubkey, blockhash)
    
    return TransactionResponse(transaction_b64=unsigned_tx_b64)

class PurchaseRequest(BaseModel):
    months: int
    supporter_token_account: str
    athlete_token_account: str

@router.post("/{plan_id}/transaction/purchase", response_model=TransactionResponse)
async def get_purchase_subscription_transaction(
    plan_id: uuid.UUID,
    payload: PurchaseRequest,
    user: CurrentUserDep, 
    session: SessionDep
) -> TransactionResponse:
    """Generates the unsigned transaction for a supporter to purchase subscription months."""
    
    if payload.months <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Must purchase at least 1 month"
        )

    # Fetch the plan to ensure it exists and is published
    plan = await session.scalar(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
    if not plan or plan.status != "published":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active plan not found")

    # The athlete's wallet lives on the linked profile; AthleteProfile holds only
    # public presentation fields.
    athlete = await session.scalar(
        select(AthleteProfile).where(AthleteProfile.id == plan.athlete_profile_id)
    )
    if athlete is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Athlete not found")
    athlete_profile = await session.get(Profile, athlete.profile_id)

    supporter_pubkey = Pubkey.from_string(_wallet(user.wallet))
    athlete_pubkey = Pubkey.from_string(
        _wallet(athlete_profile.wallet if athlete_profile else None)
    )

    # We need the plan's PDA to pass into the instruction
    plan_pda_pubkey, _ = plan_pda(PROGRAM_ID, athlete_pubkey)

    # 3. Build the purchase instruction
    ix = build_purchase_subscription_plan_ix(
        program_id=PROGRAM_ID,
        supporter=supporter_pubkey,
        plan=plan_pda_pubkey,
        supporter_token_account=Pubkey.from_string(payload.supporter_token_account),
        athlete_token_account=Pubkey.from_string(payload.athlete_token_account),
        months=payload.months
    )

    # 4. Fetch the latest blockhash
    async with SolanaRpc(RPC_URL) as rpc:
        blockhash, _ = await rpc.get_latest_blockhash()

    # 5. Compile the base64 transaction string
    unsigned_tx_b64 = to_unsigned_transaction([ix], supporter_pubkey, blockhash)
    
    return TransactionResponse(transaction_b64=unsigned_tx_b64)

async def _athlete(user: CurrentUserDep, session: SessionDep) -> AthleteProfile:
    athlete = await session.scalar(
        select(AthleteProfile).where(AthleteProfile.profile_id == user.id)
    )
    if athlete is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Athlete profile required"
        )
    return athlete


def _out(plan: SubscriptionPlan) -> SubscriptionPlanOut:
    return SubscriptionPlanOut(
        id=plan.id,
        athlete_profile_id=plan.athlete_profile_id,
        unit_price_usdc=format_usdc_amount(plan.unit_price_atomic),
        unit_price_usdc_atomic=plan.unit_price_atomic,
        benefits=plan.benefits,
        status=plan.status,
        created_at=plan.created_at or dt.datetime.now(tz=dt.UTC),
        updated_at=plan.updated_at or dt.datetime.now(tz=dt.UTC),
    )


@router.get("/me", response_model=SubscriptionPlanOut | None)
async def read_my_plan(user: CurrentUserDep, session: SessionDep) -> SubscriptionPlanOut | None:
    athlete = await _athlete(user, session)
    plan = await session.scalar(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.athlete_profile_id == athlete.id)
        .where(SubscriptionPlan.status != "archived")
        .order_by(SubscriptionPlan.created_at.desc())
    )
    return _out(plan) if plan else None


@router.post("", response_model=SubscriptionPlanOut, status_code=status.HTTP_201_CREATED)
async def create_plan(
    payload: SubscriptionPlanCreate, user: CurrentUserDep, session: SessionDep
) -> SubscriptionPlanOut:
    athlete = await _athlete(user, session)
    existing = await session.scalar(
        select(SubscriptionPlan).where(
            SubscriptionPlan.athlete_profile_id == athlete.id,
            SubscriptionPlan.status.in_(["draft", "published"]),
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Open plan already exists")
    plan = SubscriptionPlan(
        athlete_profile_id=athlete.id,
        unit_price_atomic=parse_usdc_amount(payload.unit_price_usdc),
        benefits=payload.benefits.strip(),
        status="draft",
    )
    session.add(plan)
    await session.flush()
    return _out(plan)


@router.patch("/{plan_id}", response_model=SubscriptionPlanOut)
async def update_plan(
    plan_id: uuid.UUID,
    payload: SubscriptionPlanUpdate,
    user: CurrentUserDep,
    session: SessionDep,
) -> SubscriptionPlanOut:
    athlete = await _athlete(user, session)
    plan = await session.scalar(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == plan_id,
            SubscriptionPlan.athlete_profile_id == athlete.id,
        )
    )
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    if plan.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Published plan is immutable"
        )
    if payload.unit_price_usdc is not None:
        plan.unit_price_atomic = parse_usdc_amount(payload.unit_price_usdc)
    if payload.benefits is not None:
        plan.benefits = payload.benefits.strip()
    await session.flush()
    return _out(plan)


@router.post("/{plan_id}/publish", response_model=SubscriptionPlanOut)
async def publish_plan(
    plan_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> SubscriptionPlanOut:
    athlete = await _athlete(user, session)
    plan = await session.scalar(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == plan_id,
            SubscriptionPlan.athlete_profile_id == athlete.id,
        )
    )
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    if plan.status == "published":
        return _out(plan)
    if plan.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Archived plan cannot publish"
        )
    plan.status = "published"
    await session.flush()
    return _out(plan)


@router.post("/{plan_id}/archive", response_model=SubscriptionPlanOut)
async def archive_plan(
    plan_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> SubscriptionPlanOut:
    athlete = await _athlete(user, session)
    plan = await session.scalar(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == plan_id,
            SubscriptionPlan.athlete_profile_id == athlete.id,
        )
    )
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    if plan.status == "archived":
        return _out(plan)
    dependent_campaign = await session.scalar(
        select(Campaign.id)
        .join(CampaignPublishIntent, CampaignPublishIntent.campaign_id == Campaign.id)
        .where(Campaign.plan_id == plan.id)
    )
    if dependent_campaign is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Plan cannot be archived after campaign publication begins",
        )
    plan.status = "archived"
    await session.flush()
    return _out(plan)
