"""SQLAlchemy mirrors for the Backr domain migration.

The SQL migration remains authoritative. These models intentionally use plain
strings for database check-constrained statuses so they continue to mirror the
schema without a second enum migration source.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ProfileRole(Base):
    __tablename__ = "profile_roles"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AthleteProfile(Base):
    __tablename__ = "athlete_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), unique=True
    )
    display_name: Mapped[str] = mapped_column(Text)
    sport: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    avatar_uri: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("athlete_profiles.id", ondelete="RESTRICT")
    )
    unit_price_atomic: Mapped[int] = mapped_column(BigInteger)
    benefits: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="draft")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("athlete_profiles.id", ondelete="RESTRICT")
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    unit_price_atomic: Mapped[int] = mapped_column(BigInteger)
    minimum_success_threshold_atomic: Mapped[int] = mapped_column(BigInteger)
    main_goal_atomic: Mapped[int | None] = mapped_column(BigInteger)
    start_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    metadata_uri: Mapped[str | None] = mapped_column(Text)
    metadata_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(Text, default="draft")
    campaign_pda: Mapped[str | None] = mapped_column(Text, unique=True)
    escrow_token_account: Mapped[str | None] = mapped_column(Text, unique=True)
    chain_signature: Mapped[str | None] = mapped_column(Text, unique=True)
    nonce: Mapped[bytes | None] = mapped_column(LargeBinary, unique=True)
    publish_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    raised_amount_atomic: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CampaignStretchGoal(Base):
    __tablename__ = "campaign_stretch_goals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column()
    amount_atomic: Mapped[int] = mapped_column(BigInteger)
    benefit: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (UniqueConstraint("campaign_id", "position"),)


class CampaignRewardTier(Base):
    __tablename__ = "campaign_reward_tiers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column()
    required_units: Mapped[int] = mapped_column(BigInteger)
    benefit: Mapped[str] = mapped_column(Text)
    is_cumulative: Mapped[bool] = mapped_column(Boolean, default=True)
    reward_group: Mapped[str | None] = mapped_column(Text)
    max_supply: Mapped[int | None] = mapped_column(BigInteger)
    max_per_supporter: Mapped[int | None] = mapped_column(BigInteger)
    uri: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (UniqueConstraint("campaign_id", "position"),)


class CampaignPublishIntent(Base):
    __tablename__ = "campaign_publish_intents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), unique=True
    )
    campaign_pda: Mapped[str] = mapped_column(Text, unique=True)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    snapshot_hash: Mapped[bytes] = mapped_column(LargeBinary)
    unsigned_transaction: Mapped[str] = mapped_column(Text)
    blockhash: Mapped[str] = mapped_column(Text)
    last_valid_block_height: Mapped[int] = mapped_column(BigInteger)
    simulation_logs: Mapped[list[object]] = mapped_column(JSONB, default=list)
    confirmation_signature: Mapped[str | None] = mapped_column(Text, unique=True)
    confirmation_status: Mapped[str] = mapped_column(Text, default="pending")
    confirmation_error: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supporter_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id")
    )
    athlete_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("athlete_profiles.id")
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"))
    active_units: Mapped[int] = mapped_column(BigInteger, default=0)
    active_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (
        UniqueConstraint("supporter_profile_id", "athlete_profile_id", "campaign_id"),
    )


class Contribution(Base):
    __tablename__ = "contributions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"))
    supporter_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id")
    )
    transaction_signature: Mapped[str] = mapped_column(Text, unique=True)
    purchased_units: Mapped[int] = mapped_column(BigInteger)
    contributed_amount_atomic: Mapped[int] = mapped_column(BigInteger)
    immediate_units: Mapped[int] = mapped_column(BigInteger, default=0)
    pending_units: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(Text, default="pending")
    base_points_confirmed: Mapped[int] = mapped_column(BigInteger, default=0)
    base_points_pending: Mapped[int] = mapped_column(BigInteger, default=0)
    success_bonus_points: Mapped[int] = mapped_column(BigInteger, default=0)
    success_bonus_awarded: Mapped[bool] = mapped_column(Boolean, default=False)
    highest_reward_tier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign_reward_tiers.id")
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (Index("contributions_campaign_idx", "campaign_id", "created_at"),)


class SupportPointAccount(Base):
    __tablename__ = "support_point_accounts"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id"), primary_key=True
    )
    available_points: Mapped[int] = mapped_column(BigInteger, default=0)
    pending_points: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SupportPointLedger(Base):
    __tablename__ = "support_point_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    operation_type: Mapped[str] = mapped_column(Text)
    delta_points: Mapped[int] = mapped_column(BigInteger)
    available_balance_after: Mapped[int] = mapped_column(BigInteger)
    pending_balance_after: Mapped[int] = mapped_column(BigInteger)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id")
    )
    contribution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contributions.id")
    )
    reward_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("athlete_reward_orders.id")
    )
    source_key: Mapped[str] = mapped_column(Text, unique=True)
    transaction_reference: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CampaignRewardEntitlement(Base):
    __tablename__ = "campaign_reward_entitlements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"))
    supporter_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id")
    )
    contribution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contributions.id")
    )
    reward_tier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign_reward_tiers.id")
    )
    benefit: Mapped[str] = mapped_column(Text)
    fulfillment_type: Mapped[str] = mapped_column(Text, default="digital")
    status: Mapped[str] = mapped_column(Text, default="locked")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (UniqueConstraint("campaign_id", "supporter_profile_id", "reward_tier_id"),)


class RewardFulfillmentEvent(Base):
    """Append-only audit of every entitlement and reward order transition."""

    __tablename__ = "reward_fulfillment_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_type: Mapped[str] = mapped_column(Text)
    entitlement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign_reward_entitlements.id", ondelete="CASCADE")
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("athlete_reward_orders.id", ondelete="CASCADE")
    )
    from_status: Mapped[str | None] = mapped_column(Text)
    to_status: Mapped[str] = mapped_column(Text)
    actor_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL")
    )
    fulfillment_reference: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PlatformCosmeticItem(Base):
    __tablename__ = "platform_cosmetic_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    support_points_price: Mapped[int] = mapped_column(BigInteger)
    metadata_uri: Mapped[str | None] = mapped_column(Text)
    available_quantity: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SupporterCosmetic(Base):
    __tablename__ = "supporter_cosmetics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    cosmetic_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_cosmetic_items.id")
    )
    acquired_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (UniqueConstraint("profile_id", "cosmetic_item_id"),)


class AthleteRewardOffer(Base):
    __tablename__ = "athlete_reward_offers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("athlete_profiles.id")
    )
    reward_name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    support_points_price: Mapped[int] = mapped_column(BigInteger)
    available_quantity: Mapped[int | None] = mapped_column(BigInteger)
    maximum_per_user: Mapped[int | None] = mapped_column(BigInteger)
    availability_start: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    availability_end: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    fulfillment_type: Mapped[str] = mapped_column(Text, default="digital")
    metadata_uri: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="active")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AthleteRewardOrder(Base):
    __tablename__ = "athlete_reward_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("athlete_reward_offers.id")
    )
    supporter_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id")
    )
    points_spent: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(Text, default="reserved")
    fulfillment_details: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PayoutVestingEntry(Base):
    __tablename__ = "payout_vesting_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contribution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contributions.id")
    )
    athlete_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("athlete_profiles.id")
    )
    amount_atomic: Mapped[int] = mapped_column(BigInteger)
    release_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="scheduled")
    transaction_signature: Mapped[str | None] = mapped_column(Text, unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    released_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
