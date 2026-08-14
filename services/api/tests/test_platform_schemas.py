from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from app.domain.campaigns import CampaignValidationError, validate_campaign_draft
from app.schemas.campaigns import CampaignCreate, RewardTierInput
from app.schemas.plans import SubscriptionPlanCreate, SubscriptionPlanUpdate
from app.schemas.rewards import (
    AthleteRewardOfferUpdate,
    DigitalFulfillmentDetails,
    PhysicalFulfillmentDetails,
    RedeemRequest,
    SessionFulfillmentDetails,
)


def test_plan_schema_preserves_decimal_money_as_string() -> None:
    plan = SubscriptionPlanCreate(unit_price_usdc="25.125", benefits="Subscriber access")
    assert plan.unit_price_usdc == "25.125"


def test_plan_schema_rejects_over_precision() -> None:
    with pytest.raises(ValidationError):
        SubscriptionPlanCreate(unit_price_usdc="1.0000001", benefits="Access")


def test_draft_plan_update_can_change_exact_price() -> None:
    plan = SubscriptionPlanUpdate(unit_price_usdc="25.125", benefits=" Access ")
    assert plan.unit_price_usdc == "25.125"
    assert plan.benefits == "Access"


def test_campaign_schema_requires_timezone_aware_dates() -> None:
    with pytest.raises(ValidationError):
        CampaignCreate(
            plan_id="00000000-0000-0000-0000-000000000001",
            title="Campaign",
            description="Description",
            start_at=dt.datetime(2026, 9, 1),
            end_at=dt.datetime(2026, 10, 1, tzinfo=dt.UTC),
            minimum_success_threshold_usdc="800",
            reward_tiers=[RewardTierInput(required_units=1, benefit="Thank you")],
        )


def test_campaign_schema_rejects_blank_authoring_text() -> None:
    with pytest.raises(ValidationError):
        CampaignCreate(
            plan_id="00000000-0000-0000-0000-000000000001",
            title="   ",
            description="Description",
            start_at=dt.datetime(2026, 9, 1, tzinfo=dt.UTC),
            end_at=dt.datetime(2026, 10, 1, tzinfo=dt.UTC),
            minimum_success_threshold_usdc="800",
        )


def test_reward_tier_normalizes_a_blank_group_to_none() -> None:
    blank = RewardTierInput(required_units=1, benefit="Thanks", reward_group="  ")
    assert blank.reward_group is None
    assert RewardTierInput(required_units=1, benefit="Thanks").reward_group is None
    tier = RewardTierInput(required_units=1, benefit="Thanks", reward_group=" signed ")
    assert tier.reward_group == "signed"


def test_reward_tier_rejects_an_oversized_group() -> None:
    with pytest.raises(ValidationError):
        RewardTierInput(required_units=1, benefit="Thanks", reward_group="g" * 41)


def test_reward_tier_max_per_supporter_is_limited_to_one() -> None:
    # An entitlement is unique per (campaign, supporter, tier), so any other
    # value would be a limit the platform silently ignores.
    assert RewardTierInput(required_units=1, benefit="Thanks", max_per_supporter=1)
    with pytest.raises(ValidationError):
        RewardTierInput(required_units=1, benefit="Thanks", max_per_supporter=2)


def test_campaign_draft_rejects_a_multi_claim_tier() -> None:
    values = {
        "unit_price_atomic": 1_000_000,
        "minimum_success_threshold_atomic": 5_000_000,
        "main_goal_atomic": None,
        "stretch_goals_atomic": [],
        "start_at": dt.datetime(2026, 9, 1, tzinfo=dt.UTC),
        "end_at": dt.datetime(2026, 10, 1, tzinfo=dt.UTC),
        "reward_tiers": [{"required_units": 1, "benefit": "Thanks", "max_per_supporter": 2}],
    }
    with pytest.raises(CampaignValidationError):
        validate_campaign_draft(values)

    values["reward_tiers"] = [{"required_units": 1, "benefit": "Thanks", "max_per_supporter": 1}]
    validate_campaign_draft(values)


def test_offer_update_rejects_unknown_fields() -> None:
    assert AthleteRewardOfferUpdate(status="archived").status == "archived"
    with pytest.raises(ValidationError):
        AthleteRewardOfferUpdate(fulfillment_type="physical")
    with pytest.raises(ValidationError):
        AthleteRewardOfferUpdate(status="retired")


def test_redeem_request_requires_a_usable_idempotency_key() -> None:
    assert RedeemRequest().idempotency_key is None
    assert RedeemRequest(idempotency_key="a" * 12).idempotency_key == "a" * 12
    with pytest.raises(ValidationError):
        RedeemRequest(idempotency_key="short")


def test_fulfillment_details_collect_only_their_own_fields() -> None:
    DigitalFulfillmentDetails(delivery_handle="supporter@example.com")
    SessionFulfillmentDetails(preferred_times="Weekday evenings", contact_handle="@supporter")
    PhysicalFulfillmentDetails(
        recipient_name="A Supporter",
        address_line1="1 Example Street",
        city="Lisbon",
        postal_code="1000-001",
        country="Portugal",
    )

    # A physical address must never ride along on a digital reward.
    with pytest.raises(ValidationError):
        DigitalFulfillmentDetails(
            delivery_handle="supporter@example.com", address_line1="1 Example Street"
        )
    with pytest.raises(ValidationError):
        SessionFulfillmentDetails(
            preferred_times="Weekends", contact_handle="@supporter", postal_code="1000-001"
        )
    with pytest.raises(ValidationError):
        PhysicalFulfillmentDetails(recipient_name="A Supporter", address_line1="1 Example Street")
