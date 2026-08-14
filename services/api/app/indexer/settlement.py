"""Project on-chain purchase and settlement events into the supporter read model.

Entitlements are granted from a supporter's *confirmed* units only, which is why
`sync_entitlements` reads `Subscription.active_units` rather than any per
contribution figure: escrowed pending units are not value the chain has released.

Every writer that grants entitlements must already hold `FOR UPDATE` on the
campaign row. That lock is the entire reason the `max_supply` count below is
safe - it serialises supply checks per campaign without a counter column, and
nothing at the call site makes that requirement visible.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import CursorResult, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.rewards import eligible_tier_positions
from app.domain.settlement import BASE_POINTS_PER_UNIT, calculate_success_bonus
from app.indexer.events import CampaignEvent
from app.models import Profile
from app.platform_models import (
    Campaign,
    CampaignRewardEntitlement,
    CampaignRewardTier,
    Contribution,
    Subscription,
    SupportPointAccount,
    SupportPointLedger,
)


async def sync_entitlements(
    session: AsyncSession,
    campaign: Campaign,
    supporter_profile_id: uuid.UUID,
    confirmed_units: int,
    contribution_id: uuid.UUID,
) -> int:
    """Grant every tier the supporter's confirmed units unlock.

    The caller must already hold `FOR UPDATE` on `campaign`. Idempotent, and
    never revokes: a tier that has been granted stays granted, and a cancelled
    entitlement is never resurrected because the conflict target already exists.

    Returns the number of entitlements newly granted.
    """
    tiers = list(
        await session.scalars(
            select(CampaignRewardTier)
            .where(CampaignRewardTier.campaign_id == campaign.id)
            .order_by(CampaignRewardTier.position)
        )
    )
    if not tiers:
        return 0

    unlocked = eligible_tier_positions(
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
    if not unlocked:
        return 0

    granted = 0
    for index in unlocked:
        tier = tiers[index]
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
            # A sold-out tier is simply not granted. Recording a cancelled row
            # instead would consume the unique slot and permanently block a
            # re-grant if an athlete later cancels someone else's entitlement.
            if claimed >= tier.max_supply:
                continue
        statement = (
            insert(CampaignRewardEntitlement)
            .values(
                campaign_id=campaign.id,
                supporter_profile_id=supporter_profile_id,
                contribution_id=contribution_id,
                reward_tier_id=tier.id,
                benefit=tier.benefit,
                fulfillment_type="digital",
                status="unlocked",
            )
            .on_conflict_do_nothing(
                index_elements=["campaign_id", "supporter_profile_id", "reward_tier_id"]
            )
        )
        result = cast(CursorResult[Any], await session.execute(statement))
        granted += result.rowcount or 0

    # Record the highest tier the supporter actually holds, not the highest they
    # qualified for: a sold-out tier is unlocked but never granted, and claiming
    # otherwise would misreport what they own.
    contribution = await session.get(Contribution, contribution_id)
    if contribution is not None:
        contribution.highest_reward_tier_id = await session.scalar(
            select(CampaignRewardEntitlement.reward_tier_id)
            .join(
                CampaignRewardTier,
                CampaignRewardTier.id == CampaignRewardEntitlement.reward_tier_id,
            )
            .where(
                CampaignRewardEntitlement.campaign_id == campaign.id,
                CampaignRewardEntitlement.supporter_profile_id == supporter_profile_id,
                CampaignRewardEntitlement.status != "cancelled",
            )
            .order_by(CampaignRewardTier.required_units.desc())
            .limit(1)
        )
    return granted


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
        # Column defaults are applied at flush, not construction, so seed the
        # counter explicitly - otherwise the first purchase increments None.
        subscription = Subscription(
            supporter_profile_id=supporter.id,
            athlete_profile_id=campaign.athlete_profile_id,
            campaign_id=campaign.id,
            active_units=0,
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
        account = SupportPointAccount(profile_id=supporter.id, available_points=0, pending_points=0)
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
    await sync_entitlements(
        session, campaign, supporter.id, subscription.active_units, contribution.id
    )
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
    subscription = await session.scalar(
        select(Subscription)
        .where(
            Subscription.supporter_profile_id == supporter.id,
            Subscription.athlete_profile_id == campaign.athlete_profile_id,
            Subscription.campaign_id == campaign.id,
        )
        .with_for_update()
    )
    changed = 0
    latest_contribution_id: uuid.UUID | None = None
    for contribution in contributions:
        pending_points = contribution.base_points_pending
        # The chain promoted these units; capture the count before zeroing it so
        # the subscription can be credited below.
        promoted_units = contribution.pending_units
        if pending_points <= 0:
            contribution.pending_units = 0
            continue
        account.pending_points = max(account.pending_points - pending_points, 0)
        contribution.pending_units = 0
        if event.successful:
            account.available_points += pending_points
            base_points = contribution.base_points_confirmed + pending_points
            bonus = calculate_success_bonus(base_points, bonus_rate_bps)
            contribution.base_points_confirmed = base_points
            contribution.success_bonus_points = bonus
            contribution.success_bonus_awarded = True
            contribution.status = "confirmed"
            if subscription is not None:
                subscription.active_units += promoted_units
            latest_contribution_id = contribution.id
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
    # A failed settlement needs no entitlement cleanup: grants only ever came
    # from active_units, which never contained the refunded pending units.
    if event.successful and subscription is not None and latest_contribution_id is not None:
        await sync_entitlements(
            session, campaign, supporter.id, subscription.active_units, latest_contribution_id
        )
        await session.flush()
    return changed
