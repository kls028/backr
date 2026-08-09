"""Platform cosmetics and athlete-created Support Point offers."""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.auth import CurrentUserDep
from app.db import SessionDep
from app.domain.rewards import RewardValidationError, reserve_points
from app.platform_models import (
    AthleteRewardOffer,
    AthleteRewardOrder,
    PlatformCosmeticItem,
    SupporterCosmetic,
    SupportPointAccount,
    SupportPointLedger,
)
from app.routers.plans import _athlete
from app.schemas.rewards import (
    AthleteRewardOfferCreate,
    AthleteRewardOfferOut,
    AthleteRewardOrderOut,
    CosmeticItemOut,
    CosmeticOrderOut,
)

router = APIRouter(tags=["rewards"])


def _offer_out(offer: AthleteRewardOffer) -> AthleteRewardOfferOut:
    return AthleteRewardOfferOut.model_validate(offer)


@router.get("/store/cosmetics", response_model=list[CosmeticItemOut])
async def list_cosmetics(session: SessionDep) -> list[CosmeticItemOut]:
    items = list(
        await session.scalars(
            select(PlatformCosmeticItem)
            .where(
                (PlatformCosmeticItem.available_quantity.is_(None))
                | (PlatformCosmeticItem.available_quantity > 0)
            )
            .order_by(PlatformCosmeticItem.created_at.desc(), PlatformCosmeticItem.id.desc())
        )
    )
    return [CosmeticItemOut.model_validate(item) for item in items]


@router.post("/store/cosmetics/{item_id}/redeem", response_model=CosmeticOrderOut)
async def redeem_cosmetic(
    item_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> CosmeticOrderOut:
    item = await session.scalar(
        select(PlatformCosmeticItem).where(PlatformCosmeticItem.id == item_id).with_for_update()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cosmetic not found")
    existing = await session.scalar(
        select(SupporterCosmetic).where(
            SupporterCosmetic.profile_id == user.id,
            SupporterCosmetic.cosmetic_item_id == item.id,
        )
    )
    account = await session.scalar(
        select(SupportPointAccount)
        .where(SupportPointAccount.profile_id == user.id)
        .with_for_update()
    )
    if existing is not None and account is not None:
        return CosmeticOrderOut(
            id=existing.id,
            cosmetic_item_id=item.id,
            points_spent=0,
            available_points_after=account.available_points,
            acquired_at=existing.acquired_at or dt.datetime.now(tz=dt.UTC),
        )
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="No Support Points available"
        )
    try:
        remaining = reserve_points(account.available_points, item.support_points_price)
    except RewardValidationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if item.available_quantity is not None and item.available_quantity <= 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cosmetic is unavailable")

    account.available_points = remaining
    if item.available_quantity is not None:
        item.available_quantity -= 1
    acquired = SupporterCosmetic(profile_id=user.id, cosmetic_item_id=item.id)
    session.add(acquired)
    await session.flush()
    session.add(
        SupportPointLedger(
            profile_id=user.id,
            operation_type="redeemed",
            delta_points=-item.support_points_price,
            available_balance_after=remaining,
            pending_balance_after=account.pending_points,
            source_key=f"cosmetic:{user.id}:{item.id}",
        )
    )
    await session.flush()
    return CosmeticOrderOut(
        id=acquired.id,
        cosmetic_item_id=item.id,
        points_spent=item.support_points_price,
        available_points_after=remaining,
        acquired_at=acquired.acquired_at or dt.datetime.now(tz=dt.UTC),
    )


@router.get("/reward-offers", response_model=list[AthleteRewardOfferOut])
async def list_reward_offers(session: SessionDep) -> list[AthleteRewardOfferOut]:
    offers = list(
        await session.scalars(
            select(AthleteRewardOffer)
            .where(AthleteRewardOffer.status == "active")
            .order_by(AthleteRewardOffer.created_at.desc(), AthleteRewardOffer.id.desc())
        )
    )
    return [_offer_out(offer) for offer in offers]


@router.get("/athlete/reward-offers", response_model=list[AthleteRewardOfferOut])
async def list_my_reward_offers(
    user: CurrentUserDep, session: SessionDep
) -> list[AthleteRewardOfferOut]:
    athlete = await _athlete(user, session)
    offers = list(
        await session.scalars(
            select(AthleteRewardOffer)
            .where(AthleteRewardOffer.athlete_profile_id == athlete.id)
            .order_by(AthleteRewardOffer.created_at.desc(), AthleteRewardOffer.id.desc())
        )
    )
    return [_offer_out(offer) for offer in offers]


@router.post(
    "/athlete/reward-offers",
    response_model=AthleteRewardOfferOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_reward_offer(
    payload: AthleteRewardOfferCreate, user: CurrentUserDep, session: SessionDep
) -> AthleteRewardOfferOut:
    athlete = await _athlete(user, session)
    if payload.availability_start and payload.availability_end:
        if payload.availability_end <= payload.availability_start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="availability_end must be after availability_start",
            )
    offer = AthleteRewardOffer(athlete_profile_id=athlete.id, **payload.model_dump())
    session.add(offer)
    await session.flush()
    return _offer_out(offer)


@router.post("/reward-offers/{offer_id}/redeem", response_model=AthleteRewardOrderOut)
async def redeem_reward_offer(
    offer_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> AthleteRewardOrderOut:
    offer = await session.scalar(
        select(AthleteRewardOffer).where(AthleteRewardOffer.id == offer_id).with_for_update()
    )
    if offer is None or offer.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward offer not found")
    now = dt.datetime.now(tz=dt.UTC)
    if offer.availability_start and now < offer.availability_start:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Reward is not available yet"
        )
    if offer.availability_end and now >= offer.availability_end:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Reward is no longer available"
        )
    if offer.available_quantity is not None and offer.available_quantity <= 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reward is unavailable")
    if offer.maximum_per_user is not None:
        used = (
            await session.scalar(
                select(func.count(AthleteRewardOrder.id)).where(
                    AthleteRewardOrder.offer_id == offer.id,
                    AthleteRewardOrder.supporter_profile_id == user.id,
                    AthleteRewardOrder.status != "cancelled",
                )
            )
            or 0
        )
        if used >= offer.maximum_per_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Per-user limit reached"
            )

    account = await session.scalar(
        select(SupportPointAccount)
        .where(SupportPointAccount.profile_id == user.id)
        .with_for_update()
    )
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="No Support Points available"
        )
    try:
        remaining = reserve_points(account.available_points, offer.support_points_price)
    except RewardValidationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    account.available_points = remaining
    if offer.available_quantity is not None:
        offer.available_quantity -= 1
    order = AthleteRewardOrder(
        offer_id=offer.id,
        supporter_profile_id=user.id,
        points_spent=offer.support_points_price,
        status="reserved",
    )
    session.add(order)
    await session.flush()
    session.add(
        SupportPointLedger(
            profile_id=user.id,
            operation_type="redeemed",
            delta_points=-offer.support_points_price,
            available_balance_after=remaining,
            pending_balance_after=account.pending_points,
            reward_order_id=order.id,
            source_key=f"offer:{order.id}",
        )
    )
    await session.flush()
    return AthleteRewardOrderOut.model_validate(order)
