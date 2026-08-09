"""Campaign configuration, draft editing, and public read APIs."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, TypedDict

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import delete, select

from app.auth import CurrentUserDep
from app.db import SessionDep
from app.domain.campaigns import CampaignValidationError, validate_campaign_draft
from app.domain.money import format_usdc_amount, parse_usdc_amount
from app.platform_models import (
    Campaign,
    CampaignRewardTier,
    CampaignStretchGoal,
    SubscriptionPlan,
)
from app.routers.plans import _athlete
from app.schemas.campaigns import CampaignCreate, CampaignOut, CampaignUpdate

router = APIRouter(tags=["campaigns"])


class CampaignDraftValues(TypedDict):
    unit_price_atomic: int
    minimum_success_threshold_atomic: int
    main_goal_atomic: int | None
    stretch_goals_atomic: list[int]
    start_at: dt.datetime
    end_at: dt.datetime
    reward_tiers: list[dict[str, object]]


async def _load_children(
    session: SessionDep, campaign_id: uuid.UUID
) -> tuple[list[CampaignStretchGoal], list[CampaignRewardTier]]:
    goals = list(
        await session.scalars(
            select(CampaignStretchGoal)
            .where(CampaignStretchGoal.campaign_id == campaign_id)
            .order_by(CampaignStretchGoal.position)
        )
    )
    tiers = list(
        await session.scalars(
            select(CampaignRewardTier)
            .where(CampaignRewardTier.campaign_id == campaign_id)
            .order_by(CampaignRewardTier.position)
        )
    )
    return goals, tiers


async def _out(session: SessionDep, campaign: Campaign) -> CampaignOut:
    goals, tiers = await _load_children(session, campaign.id)
    return CampaignOut(
        id=campaign.id,
        athlete_profile_id=campaign.athlete_profile_id,
        plan_id=campaign.plan_id,
        title=campaign.title,
        description=campaign.description,
        unit_price_usdc=format_usdc_amount(campaign.unit_price_atomic),
        unit_price_usdc_atomic=campaign.unit_price_atomic,
        minimum_success_threshold_usdc=format_usdc_amount(
            campaign.minimum_success_threshold_atomic
        ),
        minimum_success_threshold_atomic=campaign.minimum_success_threshold_atomic,
        main_goal_usdc=(
            format_usdc_amount(campaign.main_goal_atomic) if campaign.main_goal_atomic else None
        ),
        main_goal_atomic=campaign.main_goal_atomic,
        start_at=campaign.start_at,
        end_at=campaign.end_at,
        metadata_uri=campaign.metadata_uri,
        metadata_hash=campaign.metadata_hash.hex() if campaign.metadata_hash else None,
        status=campaign.status,
        campaign_pda=campaign.campaign_pda,
        escrow_token_account=campaign.escrow_token_account,
        chain_signature=campaign.chain_signature,
        stretch_goals=[
            {
                "id": str(item.id),
                "amount_atomic": item.amount_atomic,
                "amount_usdc": format_usdc_amount(item.amount_atomic),
                "benefit": item.benefit,
            }
            for item in goals
        ],
        reward_tiers=[
            {
                "id": str(item.id),
                "required_units": item.required_units,
                "benefit": item.benefit,
                "is_cumulative": item.is_cumulative,
                "max_supply": item.max_supply,
                "max_per_supporter": item.max_per_supporter,
                "uri": item.uri,
            }
            for item in tiers
        ],
        created_at=campaign.created_at or dt.datetime.now(tz=dt.UTC),
        updated_at=campaign.updated_at or dt.datetime.now(tz=dt.UTC),
    )


def _draft_values(
    campaign: Campaign, payload: CampaignCreate | CampaignUpdate
) -> CampaignDraftValues:
    minimum = parse_usdc_amount(payload.minimum_success_threshold_usdc)
    main_goal = parse_usdc_amount(payload.main_goal_usdc) if payload.main_goal_usdc else None
    stretch = [parse_usdc_amount(item.amount_usdc) for item in payload.stretch_goals]
    tiers = [item.model_dump() for item in payload.reward_tiers]
    values: CampaignDraftValues = {
        "unit_price_atomic": campaign.unit_price_atomic,
        "minimum_success_threshold_atomic": minimum,
        "main_goal_atomic": main_goal,
        "stretch_goals_atomic": stretch,
        "start_at": payload.start_at,
        "end_at": payload.end_at,
        "reward_tiers": tiers,
    }
    validate_campaign_draft(values)
    return values


async def _replace_children(
    session: SessionDep, campaign_id: uuid.UUID, payload: CampaignCreate | CampaignUpdate
) -> None:
    await session.execute(
        delete(CampaignStretchGoal).where(CampaignStretchGoal.campaign_id == campaign_id)
    )
    await session.execute(
        delete(CampaignRewardTier).where(CampaignRewardTier.campaign_id == campaign_id)
    )
    for position, goal_input in enumerate(payload.stretch_goals):
        session.add(
            CampaignStretchGoal(
                campaign_id=campaign_id,
                position=position,
                amount_atomic=parse_usdc_amount(goal_input.amount_usdc),
                benefit=goal_input.benefit.strip(),
            )
        )
    for position, tier_input in enumerate(payload.reward_tiers):
        session.add(
            CampaignRewardTier(
                campaign_id=campaign_id,
                position=position,
                required_units=tier_input.required_units,
                benefit=tier_input.benefit.strip(),
                is_cumulative=tier_input.is_cumulative,
                max_supply=tier_input.max_supply,
                max_per_supporter=tier_input.max_per_supporter,
                uri=tier_input.uri,
            )
        )


@router.get("/campaigns", response_model=list[CampaignOut])
async def list_campaigns(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[CampaignOut]:
    statuses = ["scheduled", "active", "funded", "successful", "unsuccessful"]
    if status_filter is not None:
        if status_filter not in statuses:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unsupported campaign status",
            )
        statuses = [status_filter]
    campaigns = list(
        await session.scalars(
            select(Campaign)
            .where(Campaign.status.in_(statuses))
            .order_by(Campaign.created_at.desc(), Campaign.id.desc())
            .limit(limit)
        )
    )
    return [await _out(session, campaign) for campaign in campaigns]


@router.get("/campaigns/{campaign_id}", response_model=CampaignOut)
async def read_campaign(campaign_id: uuid.UUID, session: SessionDep) -> CampaignOut:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None or campaign.status == "draft":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return await _out(session, campaign)


@router.get("/athlete/campaigns", response_model=list[CampaignOut])
async def list_my_campaigns(user: CurrentUserDep, session: SessionDep) -> list[CampaignOut]:
    athlete = await _athlete(user, session)
    campaigns = list(
        await session.scalars(
            select(Campaign)
            .where(Campaign.athlete_profile_id == athlete.id)
            .order_by(Campaign.created_at.desc(), Campaign.id.desc())
        )
    )
    return [await _out(session, campaign) for campaign in campaigns]


@router.post("/athlete/campaigns", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: CampaignCreate, user: CurrentUserDep, session: SessionDep
) -> CampaignOut:
    athlete = await _athlete(user, session)
    plan = await session.scalar(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == payload.plan_id,
            SubscriptionPlan.athlete_profile_id == athlete.id,
            SubscriptionPlan.status == "published",
        )
    )
    if plan is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Published plan required")
    draft = Campaign(
        athlete_profile_id=athlete.id,
        plan_id=plan.id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        unit_price_atomic=plan.unit_price_atomic,
        minimum_success_threshold_atomic=1,
        start_at=payload.start_at,
        end_at=payload.end_at,
        metadata_uri=payload.metadata_uri,
        status="draft",
    )
    try:
        values = _draft_values(draft, payload)
    except CampaignValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    draft.minimum_success_threshold_atomic = values["minimum_success_threshold_atomic"]
    draft.main_goal_atomic = values["main_goal_atomic"]
    session.add(draft)
    await session.flush()
    await _replace_children(session, draft.id, payload)
    await session.flush()
    return await _out(session, draft)


@router.patch("/athlete/campaigns/{campaign_id}", response_model=CampaignOut)
async def update_campaign(
    campaign_id: uuid.UUID,
    payload: CampaignUpdate,
    user: CurrentUserDep,
    session: SessionDep,
) -> CampaignOut:
    athlete = await _athlete(user, session)
    campaign = await session.scalar(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.athlete_profile_id == athlete.id,
        )
    )
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if campaign.status != "draft" or campaign.publish_snapshot is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Published campaign is immutable"
        )
    try:
        values = _draft_values(campaign, payload)
    except CampaignValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    campaign.title = payload.title.strip()
    campaign.description = payload.description.strip()
    campaign.minimum_success_threshold_atomic = values["minimum_success_threshold_atomic"]
    campaign.main_goal_atomic = values["main_goal_atomic"]
    campaign.start_at = payload.start_at
    campaign.end_at = payload.end_at
    campaign.metadata_uri = payload.metadata_uri
    await _replace_children(session, campaign.id, payload)
    await session.flush()
    return await _out(session, campaign)


@router.post("/athlete/campaigns/{campaign_id}/cancel", response_model=CampaignOut)
async def cancel_campaign(
    campaign_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> CampaignOut:
    athlete = await _athlete(user, session)
    campaign = await session.scalar(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.athlete_profile_id == athlete.id,
        )
    )
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if campaign.status not in ("draft", "scheduled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Campaign cannot be cancelled"
        )
    campaign.status = "cancelled"
    await session.flush()
    return await _out(session, campaign)
