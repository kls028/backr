"""Reward entitlement and order fulfillment workflows.

Authorization here is expressed in the query, never in RLS: the API connects with
a service-role credential that bypasses every policy, so an ownership join is the
only thing standing between one athlete and another athlete's supporter details.
Rows the caller does not own return 404 rather than 403 so existence does not leak.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import select

from app.auth import CurrentUserDep
from app.db import SessionDep
from app.domain.fulfillment import (
    FulfillmentValidationError,
    OrderStatus,
    allowed_entitlement_targets,
    allowed_order_targets,
    parse_entitlement_status,
    parse_order_status,
    transition_entitlement,
    transition_order,
)
from app.domain.rewards import RewardValidationError, credit_points
from app.models import Profile
from app.platform_models import (
    AthleteRewardOffer,
    AthleteRewardOrder,
    Campaign,
    CampaignRewardEntitlement,
    CampaignRewardTier,
    RewardFulfillmentEvent,
    SupportPointAccount,
    SupportPointLedger,
)
from app.routers.plans import _athlete
from app.schemas.rewards import (
    FULFILLMENT_DETAIL_MODELS,
    AthleteRewardOrderQueueOut,
    EntitlementOut,
    EntitlementTransition,
    FulfillmentDetailsRequest,
    RewardOrderTransition,
)

router = APIRouter(tags=["fulfillment"])


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)


def _order_out(
    order: AthleteRewardOrder,
    offer: AthleteRewardOffer,
    supporter_display_name: str | None,
) -> AthleteRewardOrderQueueOut:
    return AthleteRewardOrderQueueOut(
        id=order.id,
        offer_id=offer.id,
        offer_name=offer.reward_name,
        fulfillment_type=offer.fulfillment_type,
        supporter_profile_id=order.supporter_profile_id,
        supporter_display_name=supporter_display_name,
        points_spent=order.points_spent,
        status=order.status,
        fulfillment_details=order.fulfillment_details,
        allowed_transitions=sorted(
            target.value
            for target in allowed_order_targets(
                parse_order_status(order.status), offer.fulfillment_type
            )
        ),
        created_at=order.created_at or _now(),
        updated_at=order.updated_at or _now(),
    )


def _entitlement_out(
    entitlement: CampaignRewardEntitlement,
    campaign_title: str,
    required_units: int,
    supporter_display_name: str | None,
) -> EntitlementOut:
    return EntitlementOut(
        id=entitlement.id,
        campaign_id=entitlement.campaign_id,
        campaign_title=campaign_title,
        reward_tier_id=entitlement.reward_tier_id,
        required_units=required_units,
        benefit=entitlement.benefit,
        fulfillment_type=entitlement.fulfillment_type,
        status=entitlement.status,
        allowed_transitions=sorted(
            target.value
            for target in allowed_entitlement_targets(parse_entitlement_status(entitlement.status))
        ),
        supporter_profile_id=entitlement.supporter_profile_id,
        supporter_display_name=supporter_display_name,
        created_at=entitlement.created_at or _now(),
        updated_at=entitlement.updated_at or _now(),
    )


def _record(
    session: SessionDep,
    *,
    subject_type: str,
    entitlement_id: uuid.UUID | None,
    order_id: uuid.UUID | None,
    from_status: str,
    to_status: str,
    actor_profile_id: uuid.UUID,
    fulfillment_reference: str | None,
    note: str | None,
) -> None:
    session.add(
        RewardFulfillmentEvent(
            subject_type=subject_type,
            entitlement_id=entitlement_id,
            order_id=order_id,
            from_status=from_status,
            to_status=to_status,
            actor_profile_id=actor_profile_id,
            fulfillment_reference=fulfillment_reference,
            note=note,
        )
    )


# ---------------------------------------------------------------------------
# Supporter-owned entitlements
# ---------------------------------------------------------------------------


@router.get("/supporter/entitlements", response_model=list[EntitlementOut])
async def list_my_entitlements(
    user: CurrentUserDep, session: SessionDep
) -> list[EntitlementOut]:
    rows = (
        await session.execute(
            select(CampaignRewardEntitlement, Campaign, CampaignRewardTier)
            .join(Campaign, Campaign.id == CampaignRewardEntitlement.campaign_id)
            .join(
                CampaignRewardTier,
                CampaignRewardTier.id == CampaignRewardEntitlement.reward_tier_id,
            )
            .where(CampaignRewardEntitlement.supporter_profile_id == user.id)
            .order_by(
                CampaignRewardEntitlement.created_at.desc(),
                CampaignRewardEntitlement.id.desc(),
            )
        )
    ).all()
    return [
        _entitlement_out(entitlement, campaign.title, tier.required_units, None)
        for entitlement, campaign, tier in rows
    ]


# ---------------------------------------------------------------------------
# Athlete fulfillment queue
# ---------------------------------------------------------------------------


@router.get("/athlete/reward-orders", response_model=list[AthleteRewardOrderQueueOut])
async def list_reward_order_queue(
    user: CurrentUserDep,
    session: SessionDep,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[AthleteRewardOrderQueueOut]:
    athlete = await _athlete(user, session)
    statement = (
        select(AthleteRewardOrder, AthleteRewardOffer, Profile)
        .join(AthleteRewardOffer, AthleteRewardOffer.id == AthleteRewardOrder.offer_id)
        .join(Profile, Profile.id == AthleteRewardOrder.supporter_profile_id)
        .where(AthleteRewardOffer.athlete_profile_id == athlete.id)
        .order_by(AthleteRewardOrder.created_at.desc(), AthleteRewardOrder.id.desc())
        .limit(limit)
    )
    if status_filter is not None:
        try:
            parse_order_status(status_filter)
        except FulfillmentValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc
        statement = statement.where(AthleteRewardOrder.status == status_filter)
    rows = (await session.execute(statement)).all()
    return [_order_out(order, offer, profile.display_name) for order, offer, profile in rows]


@router.patch("/athlete/reward-orders/{order_id}", response_model=AthleteRewardOrderQueueOut)
async def transition_reward_order(
    order_id: uuid.UUID,
    payload: RewardOrderTransition,
    user: CurrentUserDep,
    session: SessionDep,
) -> AthleteRewardOrderQueueOut:
    athlete = await _athlete(user, session)
    row = (
        await session.execute(
            select(AthleteRewardOrder, AthleteRewardOffer, Profile)
            .join(AthleteRewardOffer, AthleteRewardOffer.id == AthleteRewardOrder.offer_id)
            .join(Profile, Profile.id == AthleteRewardOrder.supporter_profile_id)
            .where(
                AthleteRewardOrder.id == order_id,
                AthleteRewardOffer.athlete_profile_id == athlete.id,
            )
            # Qualify the lock: an unqualified FOR UPDATE across this join would
            # take needless locks on the offer and profile rows.
            .with_for_update(of=AthleteRewardOrder)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward order not found")
    order, offer, profile = row

    try:
        current = parse_order_status(order.status)
        target = parse_order_status(payload.status)
        transition_order(current, target, offer.fulfillment_type)
    except FulfillmentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if target is OrderStatus.REFUNDED:
        await _refund_order(session, order, offer)

    order.status = target.value
    _record(
        session,
        subject_type="order",
        entitlement_id=None,
        order_id=order.id,
        from_status=current.value,
        to_status=target.value,
        actor_profile_id=user.id,
        fulfillment_reference=payload.fulfillment_reference,
        note=payload.note,
    )
    await session.flush()
    return _order_out(order, offer, profile.display_name)


async def _refund_order(
    session: SessionDep, order: AthleteRewardOrder, offer: AthleteRewardOffer
) -> None:
    """Return the reserved points and the inventory unit.

    Locks offer then account, matching the order the redeem path takes. Reversing
    that order here would deadlock the two paths against each other.
    """
    locked_offer = await session.scalar(
        select(AthleteRewardOffer).where(AthleteRewardOffer.id == offer.id).with_for_update()
    )
    account = await session.scalar(
        select(SupportPointAccount)
        .where(SupportPointAccount.profile_id == order.supporter_profile_id)
        .with_for_update()
    )
    if account is None:
        account = SupportPointAccount(
            profile_id=order.supporter_profile_id, available_points=0, pending_points=0
        )
        session.add(account)
        await session.flush()
    try:
        account.available_points = credit_points(account.available_points, order.points_spent)
    except RewardValidationError as exc:  # pragma: no cover - points_spent is checked > 0 in SQL
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if locked_offer is not None and locked_offer.available_quantity is not None:
        locked_offer.available_quantity += 1
    session.add(
        SupportPointLedger(
            profile_id=order.supporter_profile_id,
            operation_type="refunded",
            delta_points=order.points_spent,
            available_balance_after=account.available_points,
            pending_balance_after=account.pending_points,
            reward_order_id=order.id,
            # 'refunded' is shared with the settlement projector, which writes a
            # negative delta for removed pending points. The source_key namespace
            # is what keeps the two apart.
            source_key=f"offer-refund:{order.id}",
        )
    )


@router.patch(
    "/supporter/reward-orders/{order_id}/details", response_model=AthleteRewardOrderQueueOut
)
async def submit_fulfillment_details(
    order_id: uuid.UUID,
    payload: FulfillmentDetailsRequest,
    user: CurrentUserDep,
    session: SessionDep,
) -> AthleteRewardOrderQueueOut:
    """The one supporter-driven transition: supply delivery details to start work."""
    row = (
        await session.execute(
            select(AthleteRewardOrder, AthleteRewardOffer, Profile)
            .join(AthleteRewardOffer, AthleteRewardOffer.id == AthleteRewardOrder.offer_id)
            .join(Profile, Profile.id == AthleteRewardOrder.supporter_profile_id)
            .where(
                AthleteRewardOrder.id == order_id,
                AthleteRewardOrder.supporter_profile_id == user.id,
            )
            .with_for_update(of=AthleteRewardOrder)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward order not found")
    order, offer, profile = row
    if order.status != OrderStatus.AWAITING_DETAILS.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reward order is not awaiting fulfillment details",
        )

    model = FULFILLMENT_DETAIL_MODELS.get(offer.fulfillment_type)
    if model is None:  # pragma: no cover - fulfillment_type is check-constrained
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported fulfillment type"
        )
    try:
        details = model.model_validate(payload.details)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()
        ) from exc

    order.fulfillment_details = details.model_dump()
    order.status = OrderStatus.IN_PROGRESS.value
    _record(
        session,
        subject_type="order",
        entitlement_id=None,
        order_id=order.id,
        from_status=OrderStatus.AWAITING_DETAILS.value,
        to_status=OrderStatus.IN_PROGRESS.value,
        actor_profile_id=user.id,
        fulfillment_reference=None,
        note=None,
    )
    await session.flush()
    return _order_out(order, offer, profile.display_name)


# ---------------------------------------------------------------------------
# Athlete entitlement fulfillment
# ---------------------------------------------------------------------------


@router.get("/athlete/entitlements", response_model=list[EntitlementOut])
async def list_campaign_entitlements(
    user: CurrentUserDep,
    session: SessionDep,
    campaign_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[EntitlementOut]:
    athlete = await _athlete(user, session)
    statement = (
        select(CampaignRewardEntitlement, Campaign, CampaignRewardTier, Profile)
        .join(Campaign, Campaign.id == CampaignRewardEntitlement.campaign_id)
        .join(
            CampaignRewardTier, CampaignRewardTier.id == CampaignRewardEntitlement.reward_tier_id
        )
        .join(Profile, Profile.id == CampaignRewardEntitlement.supporter_profile_id)
        .where(Campaign.athlete_profile_id == athlete.id)
        .order_by(
            CampaignRewardEntitlement.created_at.desc(), CampaignRewardEntitlement.id.desc()
        )
        .limit(limit)
    )
    if campaign_id is not None:
        statement = statement.where(CampaignRewardEntitlement.campaign_id == campaign_id)
    rows = (await session.execute(statement)).all()
    return [
        _entitlement_out(entitlement, campaign.title, tier.required_units, profile.display_name)
        for entitlement, campaign, tier, profile in rows
    ]


@router.patch("/athlete/entitlements/{entitlement_id}", response_model=EntitlementOut)
async def transition_campaign_entitlement(
    entitlement_id: uuid.UUID,
    payload: EntitlementTransition,
    user: CurrentUserDep,
    session: SessionDep,
) -> EntitlementOut:
    athlete = await _athlete(user, session)
    row = (
        await session.execute(
            select(CampaignRewardEntitlement, Campaign, CampaignRewardTier, Profile)
            .join(Campaign, Campaign.id == CampaignRewardEntitlement.campaign_id)
            .join(
                CampaignRewardTier,
                CampaignRewardTier.id == CampaignRewardEntitlement.reward_tier_id,
            )
            .join(Profile, Profile.id == CampaignRewardEntitlement.supporter_profile_id)
            .where(
                CampaignRewardEntitlement.id == entitlement_id,
                Campaign.athlete_profile_id == athlete.id,
            )
            .with_for_update(of=CampaignRewardEntitlement)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entitlement not found")
    entitlement, campaign, tier, profile = row

    try:
        current = parse_entitlement_status(entitlement.status)
        target = parse_entitlement_status(payload.status)
        transition_entitlement(current, target)
    except FulfillmentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    entitlement.status = target.value
    _record(
        session,
        subject_type="entitlement",
        entitlement_id=entitlement.id,
        order_id=None,
        from_status=current.value,
        to_status=target.value,
        actor_profile_id=user.id,
        fulfillment_reference=payload.fulfillment_reference,
        note=payload.note,
    )
    await session.flush()
    return _entitlement_out(entitlement, campaign.title, tier.required_units, profile.display_name)
