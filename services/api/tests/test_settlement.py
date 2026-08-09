import datetime as dt

import pytest

from app.domain.settlement import (
    BASE_POINTS_PER_UNIT,
    SettlementValidationError,
    allocate_purchase,
    calculate_success_bonus,
    settle_failure,
    settle_success,
    vesting_schedule,
)


def test_first_purchase_activates_one_unit_and_holds_the_rest() -> None:
    allocation = allocate_purchase(purchased_units=3, active_units=0)

    assert allocation.immediate_units == 1
    assert allocation.pending_units == 2
    assert allocation.confirmed_points == BASE_POINTS_PER_UNIT
    assert allocation.pending_points == 2 * BASE_POINTS_PER_UNIT


def test_additional_purchase_respects_existing_active_limit() -> None:
    allocation = allocate_purchase(purchased_units=4, active_units=12, active_unit_limit=12)

    assert allocation.immediate_units == 0
    assert allocation.pending_units == 4
    assert allocation.confirmed_points == 0
    assert allocation.pending_points == 4 * BASE_POINTS_PER_UNIT


def test_success_settlement_releases_pending_units_and_adds_bonus() -> None:
    result = settle_success(immediate_units=1, pending_units=2, bonus_rate_bps=2_000)

    assert result.activated_units == 3
    assert result.refunded_units == 0
    assert result.bonus_points == 60
    assert result.confirmed_points == 360


def test_failure_refunds_pending_units_but_keeps_immediate_unit() -> None:
    result = settle_failure(immediate_units=1, pending_units=2)

    assert result.activated_units == 1
    assert result.refunded_units == 2
    assert result.confirmed_points == BASE_POINTS_PER_UNIT
    assert result.removed_pending_points == 2 * BASE_POINTS_PER_UNIT


def test_vesting_schedule_is_exact_and_ends_at_total_amount() -> None:
    start = dt.datetime(2026, 1, 31, tzinfo=dt.UTC)
    entries = vesting_schedule(1_000_000, start, months=4, kind="standard")

    assert len(entries) == 4
    assert sum(item.amount_atomic for item in entries) == 1_000_000
    assert entries[-1].release_at > entries[0].release_at


def test_invalid_settlement_inputs_are_rejected() -> None:
    with pytest.raises(SettlementValidationError):
        allocate_purchase(purchased_units=0, active_units=0)
    with pytest.raises(SettlementValidationError):
        calculate_success_bonus(-1, 2_000)
