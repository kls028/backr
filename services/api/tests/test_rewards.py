import pytest

from app.domain.rewards import (
    RewardValidationError,
    credit_points,
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


def test_mixed_tiers_return_ascending_positions() -> None:
    # Regression: appending the surviving non-cumulative tier after the
    # cumulative ones used to emit [2, 1] here.
    tiers = [
        {"required_units": 1, "is_cumulative": False},
        {"required_units": 2, "is_cumulative": False},
        {"required_units": 3, "is_cumulative": True},
    ]

    assert eligible_tier_positions(tiers, 4) == [1, 2]


def test_each_named_group_exposes_its_own_highest_tier() -> None:
    tiers = [
        {"required_units": 1, "is_cumulative": False, "reward_group": "signed"},
        {"required_units": 2, "is_cumulative": False, "reward_group": "signed"},
        {"required_units": 3, "is_cumulative": False, "reward_group": "visit"},
        {"required_units": 4, "is_cumulative": False, "reward_group": "visit"},
    ]

    assert eligible_tier_positions(tiers, 10) == [1, 3]


def test_ungrouped_non_cumulative_tiers_share_the_default_group() -> None:
    tiers = [
        {"required_units": 1, "is_cumulative": False},
        {"required_units": 2, "is_cumulative": False, "reward_group": None},
        {"required_units": 3, "is_cumulative": False, "reward_group": "named"},
    ]

    assert eligible_tier_positions(tiers, 10) == [1, 2]


def test_pending_units_cannot_unlock_a_tier() -> None:
    tiers = [{"required_units": 3, "is_cumulative": True}]

    assert eligible_tier_positions(tiers, 1) == []
    assert eligible_tier_positions(tiers, 0) == []
    assert eligible_tier_positions(tiers, 3) == [0]


def test_tier_validation_rejects_malformed_input() -> None:
    with pytest.raises(RewardValidationError):
        eligible_tier_positions([{"required_units": 0}], 5)
    with pytest.raises(RewardValidationError):
        eligible_tier_positions([{"required_units": 1, "is_cumulative": "yes"}], 5)
    with pytest.raises(RewardValidationError):
        eligible_tier_positions([{"required_units": 1, "reward_group": ""}], 5)
    with pytest.raises(RewardValidationError):
        eligible_tier_positions([{"required_units": 1}], -1)


def test_points_purchase_requires_enough_available_points() -> None:
    assert points_purchase(600, 250) == 350
    assert reserve_points(250, 250) == 0
    with pytest.raises(RewardValidationError):
        reserve_points(249, 250)


def test_credit_points_returns_the_refunded_balance() -> None:
    assert credit_points(0, 250) == 250
    assert credit_points(100, 250) == 350
    with pytest.raises(RewardValidationError):
        credit_points(100, 0)
    with pytest.raises(RewardValidationError):
        credit_points(-1, 250)
