"""Support Point reward eligibility and reservation rules."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


class RewardValidationError(ValueError):
    """Raised when a points or tier operation cannot be completed."""


def eligible_tier_positions(
    tiers: Sequence[Mapping[str, object]],
    confirmed_units: int,
) -> list[int]:
    if not isinstance(confirmed_units, int) or confirmed_units < 0:
        raise RewardValidationError("confirmed_units must be non-negative")

    unlocked: list[int] = []
    for index, tier in enumerate(tiers):
        required = tier.get("required_units")
        cumulative = tier.get("is_cumulative", True)
        if not isinstance(required, int) or required <= 0:
            raise RewardValidationError("required_units must be positive")
        if not isinstance(cumulative, bool):
            raise RewardValidationError("is_cumulative must be boolean")
        if required <= confirmed_units:
            unlocked.append(index)
    if not unlocked:
        return []
    if all(bool(tiers[index].get("is_cumulative", True)) for index in unlocked):
        return unlocked
    highest_non_cumulative = max(
        (index for index in unlocked if not bool(tiers[index].get("is_cumulative", True))),
        default=-1,
    )
    cumulative = [index for index in unlocked if bool(tiers[index].get("is_cumulative", True))]
    return cumulative + ([highest_non_cumulative] if highest_non_cumulative >= 0 else [])


def reserve_points(available_points: int, price: int) -> int:
    if not isinstance(available_points, int) or available_points < 0:
        raise RewardValidationError("available_points must be non-negative")
    if not isinstance(price, int) or price <= 0:
        raise RewardValidationError("price must be positive")
    if available_points < price:
        raise RewardValidationError("insufficient available points")
    return available_points - price


def points_purchase(available_points: int, price: int) -> int:
    """Return the post-purchase available balance."""
    return reserve_points(available_points, price)
