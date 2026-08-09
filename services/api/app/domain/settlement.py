"""Deterministic subscription accounting rules.

The database and chain projections call these functions, but neither owns the
business rule. Keeping allocation and settlement pure makes replay, retries,
and reconciliation safe to test independently of RPC or Postgres.
"""

from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass

BASE_POINTS_PER_UNIT = 100
MAX_BPS = 10_000


class SettlementValidationError(ValueError):
    """Raised when subscription accounting inputs are inconsistent."""


@dataclass(frozen=True, slots=True)
class PurchaseAllocation:
    immediate_units: int
    pending_units: int
    confirmed_points: int
    pending_points: int


@dataclass(frozen=True, slots=True)
class SettlementResult:
    activated_units: int
    refunded_units: int
    confirmed_points: int
    removed_pending_points: int
    bonus_points: int = 0


@dataclass(frozen=True, slots=True)
class VestingEntry:
    amount_atomic: int
    release_at: dt.datetime
    kind: str


def _positive_int(value: int, label: str) -> None:
    if not isinstance(value, int) or value <= 0:
        raise SettlementValidationError(f"{label} must be a positive integer")


def allocate_purchase(
    purchased_units: int,
    active_units: int,
    active_unit_limit: int = 12,
) -> PurchaseAllocation:
    """Allocate purchased units into immediate and pending buckets."""
    _positive_int(purchased_units, "purchased_units")
    if not isinstance(active_units, int) or active_units < 0:
        raise SettlementValidationError("active_units must be a non-negative integer")
    _positive_int(active_unit_limit, "active_unit_limit")
    # A supporter receives one immediately activated unit for a campaign. Any
    # additional units remain in escrow until settlement, and a supporter who
    # already has an active unit cannot create another immediate unit.
    remaining_capacity = max(active_unit_limit - active_units, 0)
    immediate = 1 if active_units == 0 and remaining_capacity > 0 else 0
    immediate = min(immediate, purchased_units)
    pending = purchased_units - immediate
    return PurchaseAllocation(
        immediate_units=immediate,
        pending_units=pending,
        confirmed_points=immediate * BASE_POINTS_PER_UNIT,
        pending_points=pending * BASE_POINTS_PER_UNIT,
    )


def calculate_success_bonus(base_points: int, bonus_rate_bps: int) -> int:
    """Calculate a floor-rounded bonus without floating-point arithmetic."""
    if not isinstance(base_points, int) or base_points < 0:
        raise SettlementValidationError("base_points must be non-negative")
    if not isinstance(bonus_rate_bps, int) or not 0 <= bonus_rate_bps <= MAX_BPS:
        raise SettlementValidationError("bonus_rate_bps must be between 0 and 10000")
    return base_points * bonus_rate_bps // MAX_BPS


def settle_success(
    immediate_units: int,
    pending_units: int,
    bonus_rate_bps: int,
) -> SettlementResult:
    """Promote pending units and points after a successful campaign."""
    if not isinstance(immediate_units, int) or immediate_units < 0:
        raise SettlementValidationError("immediate_units must be non-negative")
    if not isinstance(pending_units, int) or pending_units < 0:
        raise SettlementValidationError("pending_units must be non-negative")
    base_points = (immediate_units + pending_units) * BASE_POINTS_PER_UNIT
    bonus = calculate_success_bonus(base_points, bonus_rate_bps)
    return SettlementResult(
        activated_units=immediate_units + pending_units,
        refunded_units=0,
        confirmed_points=base_points + bonus,
        removed_pending_points=pending_units * BASE_POINTS_PER_UNIT,
        bonus_points=bonus,
    )


def settle_failure(immediate_units: int, pending_units: int) -> SettlementResult:
    """Refund pending units while retaining the immediately active unit."""
    if not isinstance(immediate_units, int) or immediate_units < 0:
        raise SettlementValidationError("immediate_units must be non-negative")
    if not isinstance(pending_units, int) or pending_units < 0:
        raise SettlementValidationError("pending_units must be non-negative")
    return SettlementResult(
        activated_units=immediate_units,
        refunded_units=pending_units,
        confirmed_points=immediate_units * BASE_POINTS_PER_UNIT,
        removed_pending_points=pending_units * BASE_POINTS_PER_UNIT,
    )


def _add_months(value: dt.datetime, months: int) -> dt.datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def vesting_schedule(
    amount_atomic: int,
    start_at: dt.datetime,
    months: int,
    kind: str,
) -> list[VestingEntry]:
    """Split a payout into equal monthly entries with an exact remainder."""
    _positive_int(amount_atomic, "amount_atomic")
    _positive_int(months, "months")
    if not kind.strip():
        raise SettlementValidationError("kind is required")
    base, remainder = divmod(amount_atomic, months)
    return [
        VestingEntry(
            amount_atomic=base + (1 if index < remainder else 0),
            release_at=_add_months(start_at, index + 1),
            kind=kind,
        )
        for index in range(months)
    ]
