from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from app.schemas.campaigns import CampaignCreate, RewardTierInput
from app.schemas.plans import SubscriptionPlanCreate


def test_plan_schema_preserves_decimal_money_as_string() -> None:
    plan = SubscriptionPlanCreate(unit_price_usdc="25.125", benefits="Subscriber access")
    assert plan.unit_price_usdc == "25.125"


def test_plan_schema_rejects_over_precision() -> None:
    with pytest.raises(ValidationError):
        SubscriptionPlanCreate(unit_price_usdc="1.0000001", benefits="Access")


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
