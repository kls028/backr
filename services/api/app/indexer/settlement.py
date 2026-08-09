"""Project on-chain purchase events into the supporter read model."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.settlement import BASE_POINTS_PER_UNIT, calculate_success_bonus
from app.indexer.events import CampaignEvent
from app.models import Profile
from app.platform_models import (
    Campaign,
    Contribution,
    Subscription,
    SupportPointAccount,
    SupportPointLedger,
)


async def project_purchase_event(
    session: AsyncSession,
    event: CampaignEvent,
    signature: str,
) -> uuid.UUID | None:
    """Apply a purchase once, keyed by the chain signature."""
    if event.event_type != "subscription_purchased" or event.supporter is None:
        return None
    campaign = await session.scalar(
        select(Campaign).where(Campaign.campaign_pda == event.campaign).with_for_update()
    )
    supporter = await session.scalar(select(Profile).where(Profile.wallet == event.supporter))
    if campaign is None or supporter is None:
        return None
    existing = await session.scalar(
        select(Contribution).where(Contribution.transaction_signature == signature)
    )
    if existing is not None:
        return existing.id

    contribution = Contribution(
        campaign_id=campaign.id,
        supporter_profile_id=supporter.id,
        transaction_signature=signature,
        purchased_units=event.purchased_units,
        contributed_amount_atomic=event.amount_atomic,
        immediate_units=event.immediate_units,
        pending_units=event.pending_units,
        status="confirmed",
        base_points_confirmed=event.immediate_units * BASE_POINTS_PER_UNIT,
        base_points_pending=event.pending_units * BASE_POINTS_PER_UNIT,
    )
    session.add(contribution)
    await session.flush()

    subscription = await session.scalar(
        select(Subscription)
        .where(
            Subscription.supporter_profile_id == supporter.id,
            Subscription.athlete_profile_id == campaign.athlete_profile_id,
            Subscription.campaign_id == campaign.id,
        )
        .with_for_update()
    )
    if subscription is None:
        subscription = Subscription(
            supporter_profile_id=supporter.id,
            athlete_profile_id=campaign.athlete_profile_id,
            campaign_id=campaign.id,
        )
        session.add(subscription)
    subscription.active_units += event.immediate_units
    subscription.active_until = campaign.end_at

    account = await session.scalar(
        select(SupportPointAccount)
        .where(SupportPointAccount.profile_id == supporter.id)
        .with_for_update()
    )
    if account is None:
        account = SupportPointAccount(profile_id=supporter.id)
        session.add(account)
        await session.flush()
    confirmed = event.immediate_units * BASE_POINTS_PER_UNIT
    pending = event.pending_units * BASE_POINTS_PER_UNIT
    account.available_points += confirmed
    account.pending_points += pending
    if confirmed:
        session.add(
            SupportPointLedger(
                profile_id=supporter.id,
                operation_type="confirmed",
                delta_points=confirmed,
                available_balance_after=account.available_points,
                pending_balance_after=account.pending_points,
                campaign_id=campaign.id,
                contribution_id=contribution.id,
                source_key=f"{signature}:confirmed",
                transaction_reference=signature,
            )
        )
    if pending:
        session.add(
            SupportPointLedger(
                profile_id=supporter.id,
                operation_type="pending",
                delta_points=pending,
                available_balance_after=account.available_points,
                pending_balance_after=account.pending_points,
                campaign_id=campaign.id,
                contribution_id=contribution.id,
                source_key=f"{signature}:pending",
                transaction_reference=signature,
            )
        )
    campaign.raised_amount_atomic += event.amount_atomic
    await session.flush()
    return contribution.id


async def project_settlement_event(
    session: AsyncSession,
    event: CampaignEvent,
    signature: str,
    bonus_rate_bps: int = 2_000,
) -> int:
    """Promote or refund every pending contribution for one settled position."""
    if event.event_type != "campaign_settled" or event.supporter is None:
        return 0
    campaign = await session.scalar(
        select(Campaign).where(Campaign.campaign_pda == event.campaign).with_for_update()
    )
    supporter = await session.scalar(select(Profile).where(Profile.wallet == event.supporter))
    if campaign is None or supporter is None or event.successful is None:
        return 0
    contributions = list(
        await session.scalars(
            select(Contribution)
            .where(
                Contribution.campaign_id == campaign.id,
                Contribution.supporter_profile_id == supporter.id,
                Contribution.pending_units > 0,
            )
            .with_for_update()
        )
    )
    account = await session.scalar(
        select(SupportPointAccount)
        .where(SupportPointAccount.profile_id == supporter.id)
        .with_for_update()
    )
    if account is None:
        return 0
    changed = 0
    for contribution in contributions:
        pending_points = contribution.base_points_pending
        if pending_points <= 0:
            contribution.pending_units = 0
            continue
        account.pending_points = max(account.pending_points - pending_points, 0)
        contribution.pending_units = 0
        if event.successful:
            account.available_points += pending_points
            base_points = contribution.base_points_confirmed + pending_points
            bonus = calculate_success_bonus(base_points, bonus_rate_bps)
            contribution.success_bonus_points = bonus
            contribution.success_bonus_awarded = True
            contribution.status = "confirmed"
            if pending_points:
                session.add(
                    SupportPointLedger(
                        profile_id=supporter.id,
                        operation_type="confirmed",
                        delta_points=pending_points,
                        available_balance_after=account.available_points,
                        pending_balance_after=account.pending_points,
                        campaign_id=campaign.id,
                        contribution_id=contribution.id,
                        source_key=f"{signature}:confirmed:{contribution.id}",
                        transaction_reference=signature,
                    )
                )
            if bonus:
                account.available_points += bonus
                session.add(
                    SupportPointLedger(
                        profile_id=supporter.id,
                        operation_type="success_bonus",
                        delta_points=bonus,
                        available_balance_after=account.available_points,
                        pending_balance_after=account.pending_points,
                        campaign_id=campaign.id,
                        contribution_id=contribution.id,
                        source_key=f"{signature}:bonus:{contribution.id}",
                        transaction_reference=signature,
                    )
                )
        else:
            contribution.status = "refunded"
            session.add(
                SupportPointLedger(
                    profile_id=supporter.id,
                    operation_type="refunded",
                    delta_points=-pending_points,
                    available_balance_after=account.available_points,
                    pending_balance_after=account.pending_points,
                    campaign_id=campaign.id,
                    contribution_id=contribution.id,
                    source_key=f"{signature}:refunded:{contribution.id}",
                    transaction_reference=signature,
                )
            )
        contribution.base_points_pending = 0
        changed += 1
    campaign.status = "successful" if event.successful else "unsuccessful"
    await session.flush()
    return changed
