"""Subscription-plan authoring for athlete accounts."""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.auth import CurrentUserDep
from app.db import SessionDep
from app.domain.money import format_usdc_amount, parse_usdc_amount
from app.platform_models import AthleteProfile, SubscriptionPlan
from app.schemas.plans import SubscriptionPlanCreate, SubscriptionPlanOut, SubscriptionPlanUpdate

router = APIRouter(prefix="/subscription-plans", tags=["subscription-plans"])


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
    plan.status = "archived"
    await session.flush()
    return _out(plan)
