"""Support Point reward eligibility and reservation rules."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


class RewardValidationError(ValueError):
    """Raised when a points or tier operation cannot be completed."""


def _tier_required_units(tier: Mapping[str, object]) -> int:
    required = tier.get("required_units")
    if not isinstance(required, int) or isinstance(required, bool) or required <= 0:
        raise RewardValidationError("required_units must be positive")
    return required


def _tier_is_cumulative(tier: Mapping[str, object]) -> bool:
    cumulative = tier.get("is_cumulative", True)
    if not isinstance(cumulative, bool):
        raise RewardValidationError("is_cumulative must be boolean")
    return cumulative


def _tier_group(tier: Mapping[str, object]) -> str | None:
    group = tier.get("reward_group")
    if group is None:
        return None
    if not isinstance(group, str) or not 1 <= len(group) <= 40:
        raise RewardValidationError("reward_group must be a string of 1 to 40 characters")
    return group


def eligible_tier_positions(
    tiers: Sequence[Mapping[str, object]],
    confirmed_units: int,
) -> list[int]:
    """Return the ascending indexes of the tiers unlocked by confirmed units.

    A tier unlocks when its `required_units` is at most `confirmed_units`. Every
    unlocked cumulative tier survives. Non-cumulative tiers compete within their
    `reward_group`, and only the highest unlocked tier of each group survives; a
    null `reward_group` is the shared default group.

    Only confirmed units may be passed here. Pending units are escrowed value
    that the chain has not released, so they must never reach this function.

    Supply and per-supporter limits are deliberately absent: they are mutable
    global state and belong to the projector, which enforces them while holding
    the campaign row lock.
    """
    if not isinstance(confirmed_units, int) or isinstance(confirmed_units, bool):
        raise RewardValidationError("confirmed_units must be an integer")
    if confirmed_units < 0:
        raise RewardValidationError("confirmed_units must be non-negative")

    unlocked: list[int] = []
    for index, tier in enumerate(tiers):
        required = _tier_required_units(tier)
        _tier_is_cumulative(tier)
        _tier_group(tier)
        if required <= confirmed_units:
            unlocked.append(index)

    survivors: list[int] = []
    highest_per_group: dict[str | None, int] = {}
    for index in unlocked:
        tier = tiers[index]
        if _tier_is_cumulative(tier):
            survivors.append(index)
            continue
        group = _tier_group(tier)
        incumbent = highest_per_group.get(group)
        # The database forbids duplicate required_units per campaign, but the
        # index tie-break keeps this total for any caller-supplied sequence.
        if incumbent is None or (_tier_required_units(tier), index) > (
            _tier_required_units(tiers[incumbent]),
            incumbent,
        ):
            highest_per_group[group] = index
    survivors.extend(highest_per_group.values())
    return sorted(survivors)


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


def credit_points(available_points: int, amount: int) -> int:
    """Return the post-credit available balance for a refund or reversal."""
    if not isinstance(available_points, int) or available_points < 0:
        raise RewardValidationError("available_points must be non-negative")
    if not isinstance(amount, int) or amount <= 0:
        raise RewardValidationError("amount must be positive")
    return available_points + amount
