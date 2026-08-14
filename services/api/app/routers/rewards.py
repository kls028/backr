"""Platform cosmetics, athlete Support Point offers, and supporter reward reads."""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.auth import CurrentUserDep, OptionalUserDep
from app.db import SessionDep
from app.domain.rewards import RewardValidationError, eligible_tier_positions, reserve_points
from app.platform_models import (
    AthleteProfile,
    AthleteRewardOffer,
    AthleteRewardOrder,
    Campaign,
    CampaignRewardEntitlement,
    CampaignRewardTier,
    Contribution,
    PlatformCosmeticItem,
    Subscription,
    SupporterCosmetic,
    SupportPointAccount,
    SupportPointLedger,
)
from app.routers.plans import _athlete
from app.schemas.rewards import (
    AthleteRewardOfferCreate,
    AthleteRewardOfferOut,
    AthleteRewardOfferUpdate,
    AthleteRewardOrderOut,
    CampaignRewardsOut,
    CampaignRewardTierOut,
    CosmeticItemOut,
    CosmeticOrderOut,
    OwnedCosmeticOut,
    RedeemRequest,
    SupporterRewardOrderOut,
    ViewerRewardState,
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
            # Seeded rows share one created_at, so order by price and name to keep
            # the catalog stable rather than falling back to a random uuid.
            .order_by(PlatformCosmeticItem.support_points_price, PlatformCosmeticItem.name)
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
    # Already owned is always a no-op, even when the point account row is missing.
    # Falling through would report "no points" and then violate the unique grant.
    if existing is not None:
        return CosmeticOrderOut(
            id=existing.id,
            cosmetic_item_id=item.id,
            points_spent=0,
            available_points_after=account.available_points if account is not None else 0,
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


@router.get("/supporter/cosmetics", response_model=list[OwnedCosmeticOut])
async def list_owned_cosmetics(user: CurrentUserDep, session: SessionDep) -> list[OwnedCosmeticOut]:
    rows = (
        await session.execute(
            select(SupporterCosmetic, PlatformCosmeticItem)
            .join(
                PlatformCosmeticItem,
                PlatformCosmeticItem.id == SupporterCosmetic.cosmetic_item_id,
            )
            .where(SupporterCosmetic.profile_id == user.id)
            .order_by(SupporterCosmetic.acquired_at.desc(), SupporterCosmetic.id.desc())
        )
    ).all()
    return [
        OwnedCosmeticOut(
            id=owned.id,
            cosmetic_item_id=item.id,
            name=item.name,
            description=item.description,
            metadata_uri=item.metadata_uri,
            acquired_at=owned.acquired_at or dt.datetime.now(tz=dt.UTC),
        )
        for owned, item in rows
    ]


@router.get("/campaigns/{campaign_id}/rewards", response_model=CampaignRewardsOut)
async def read_campaign_rewards(
    campaign_id: uuid.UUID, session: SessionDep, user: OptionalUserDep
) -> CampaignRewardsOut:
    """Public tier list, plus the caller's own unlock state when signed in."""
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None or campaign.status == "draft":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    tiers = list(
        await session.scalars(
            select(CampaignRewardTier)
            .where(CampaignRewardTier.campaign_id == campaign.id)
            .order_by(CampaignRewardTier.position)
        )
    )

    confirmed_units = 0
    pending_units = 0
    entitlement_ids: list[uuid.UUID] = []
    held_tier_ids: set[uuid.UUID] = set()
    if user is not None:
        confirmed_units = int(
            await session.scalar(
                select(func.coalesce(func.sum(Subscription.active_units), 0)).where(
                    Subscription.supporter_profile_id == user.id,
                    Subscription.campaign_id == campaign.id,
                )
            )
            or 0
        )
        pending_units = int(
            await session.scalar(
                select(func.coalesce(func.sum(Contribution.pending_units), 0)).where(
                    Contribution.campaign_id == campaign.id,
                    Contribution.supporter_profile_id == user.id,
                )
            )
            or 0
        )
        held = (
            await session.execute(
                select(
                    CampaignRewardEntitlement.id, CampaignRewardEntitlement.reward_tier_id
                ).where(
                    CampaignRewardEntitlement.campaign_id == campaign.id,
                    CampaignRewardEntitlement.supporter_profile_id == user.id,
                    CampaignRewardEntitlement.status != "cancelled",
                )
            )
        ).all()
        entitlement_ids = [row[0] for row in held]
        held_tier_ids = {row[1] for row in held}

    unlocked_positions = set(
        eligible_tier_positions(
            [
                {
                    "required_units": tier.required_units,
                    "is_cumulative": tier.is_cumulative,
                    "reward_group": tier.reward_group,
                }
                for tier in tiers
            ],
            confirmed_units,
        )
    )

    out: list[CampaignRewardTierOut] = []
    for index, tier in enumerate(tiers):
        supply_remaining: int | None = None
        if tier.max_supply is not None:
            claimed = (
                await session.scalar(
                    select(func.count(CampaignRewardEntitlement.id)).where(
                        CampaignRewardEntitlement.reward_tier_id == tier.id,
                        CampaignRewardEntitlement.status != "cancelled",
                    )
                )
                or 0
            )
            supply_remaining = max(tier.max_supply - claimed, 0)
        reached = tier.required_units <= confirmed_units
        unlocked = index in unlocked_positions
        out.append(
            CampaignRewardTierOut(
                id=tier.id,
                position=tier.position,
                required_units=tier.required_units,
                benefit=tier.benefit,
                is_cumulative=tier.is_cumulative,
                reward_group=tier.reward_group,
                uri=tier.uri,
                max_supply=tier.max_supply,
                supply_remaining=supply_remaining,
                unlocked_for_viewer=unlocked,
                # Reached the threshold but a higher tier in the same
                # non-cumulative group takes its place.
                superseded_for_viewer=reached and not unlocked,
                # Sold out only matters to someone who missed it; a viewer
                # holding the last unit has it, not lost it.
                unlocked_but_unavailable=(
                    unlocked and supply_remaining == 0 and tier.id not in held_tier_ids
                ),
            )
        )

    viewer = (
        ViewerRewardState(
            confirmed_units=confirmed_units,
            pending_units=pending_units,
            entitlement_ids=entitlement_ids,
        )
        if user is not None
        else None
    )
    return CampaignRewardsOut(campaign_id=campaign.id, tiers=out, viewer=viewer)


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


@router.patch("/athlete/reward-offers/{offer_id}", response_model=AthleteRewardOfferOut)
async def update_reward_offer(
    offer_id: uuid.UUID,
    payload: AthleteRewardOfferUpdate,
    user: CurrentUserDep,
    session: SessionDep,
) -> AthleteRewardOfferOut:
    athlete = await _athlete(user, session)
    # The lock is mandatory: available_quantity is also written by the redeem
    # path, and an unlocked read-modify-write here would lose that decrement.
    offer = await session.scalar(
        select(AthleteRewardOffer)
        .where(
            AthleteRewardOffer.id == offer_id,
            AthleteRewardOffer.athlete_profile_id == athlete.id,
        )
        .with_for_update()
    )
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward offer not found")

    updates = payload.model_dump(exclude_unset=True)
    start = updates.get("availability_start", offer.availability_start)
    end = updates.get("availability_end", offer.availability_end)
    if start is not None and end is not None and end <= start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="availability_end must be after availability_start",
        )
    for field, value in updates.items():
        setattr(offer, field, value)
    await session.flush()
    return _offer_out(offer)


@router.post("/reward-offers/{offer_id}/redeem", response_model=AthleteRewardOrderOut)
async def redeem_reward_offer(
    offer_id: uuid.UUID,
    user: CurrentUserDep,
    session: SessionDep,
    payload: RedeemRequest | None = None,
) -> AthleteRewardOrderOut:
    offer = await session.scalar(
        select(AthleteRewardOffer).where(AthleteRewardOffer.id == offer_id).with_for_update()
    )
    if offer is None or offer.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward offer not found")

    # Replay check runs under the offer lock so a duplicate can never reserve a
    # second unit of inventory or spend a second time.
    idempotency_key = payload.idempotency_key if payload is not None else None
    if idempotency_key is not None:
        replay = await session.scalar(
            select(AthleteRewardOrder).where(
                AthleteRewardOrder.offer_id == offer.id,
                AthleteRewardOrder.supporter_profile_id == user.id,
                AthleteRewardOrder.idempotency_key == idempotency_key,
            )
        )
        if replay is not None:
            return AthleteRewardOrderOut.model_validate(replay)

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
                    AthleteRewardOrder.status.not_in(("cancelled", "refunded")),
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
    # Physical and session rewards cannot ship until the supporter supplies
    # delivery details, so they start one step further back than digital ones.
    initial_status = "reserved" if offer.fulfillment_type == "digital" else "awaiting_details"
    order = AthleteRewardOrder(
        offer_id=offer.id,
        supporter_profile_id=user.id,
        points_spent=offer.support_points_price,
        status=initial_status,
        idempotency_key=idempotency_key,
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


@router.get("/supporter/reward-orders", response_model=list[SupporterRewardOrderOut])
async def list_my_reward_orders(
    user: CurrentUserDep, session: SessionDep
) -> list[SupporterRewardOrderOut]:
    rows = (
        await session.execute(
            select(AthleteRewardOrder, AthleteRewardOffer, AthleteProfile)
            .join(AthleteRewardOffer, AthleteRewardOffer.id == AthleteRewardOrder.offer_id)
            .join(AthleteProfile, AthleteProfile.id == AthleteRewardOffer.athlete_profile_id)
            .where(AthleteRewardOrder.supporter_profile_id == user.id)
            .order_by(AthleteRewardOrder.created_at.desc(), AthleteRewardOrder.id.desc())
        )
    ).all()
    now = dt.datetime.now(tz=dt.UTC)
    return [
        SupporterRewardOrderOut(
            id=order.id,
            offer_id=offer.id,
            offer_name=offer.reward_name,
            athlete_display_name=athlete.display_name,
            fulfillment_type=offer.fulfillment_type,
            points_spent=order.points_spent,
            status=order.status,
            fulfillment_details=order.fulfillment_details,
            created_at=order.created_at or now,
            updated_at=order.updated_at or now,
        )
        for order, offer, athlete in rows
    ]
