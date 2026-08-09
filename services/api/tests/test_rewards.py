import pytest

from app.domain.rewards import (
    RewardValidationError,
    eligible_tier_positions,
    points_purchase,
    reserve_points,
)


def test_cumulative_rewards_include_every_unlocked_tier() -> None:
    tiers = [
        {"required_units": 1, "is_cumulative": True},
        {"required_units": 3, "is_cumulative": True},
        {"required_units": 5, "is_cumulative": False},
    ]

    assert eligible_tier_positions(tiers, 4) == [0, 1]


def test_non_cumulative_rewards_only_return_highest_unlocked_tier() -> None:
    tiers = [
        {"required_units": 1, "is_cumulative": False},
        {"required_units": 3, "is_cumulative": False},
    ]

    assert eligible_tier_positions(tiers, 4) == [1]


def test_points_purchase_requires_enough_available_points() -> None:
    assert points_purchase(600, 250) == 350
    assert reserve_points(250, 250) == 0
    with pytest.raises(RewardValidationError):
        reserve_points(249, 250)
