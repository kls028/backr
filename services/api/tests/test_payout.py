import datetime as dt

from app.domain.payout import calculate_platform_fee, payout_vesting


def test_platform_fee_uses_basis_points() -> None:
    assert calculate_platform_fee(1_000_000, 500) == 50_000


def test_payout_vesting_keeps_exact_total() -> None:
    entries = payout_vesting(
        amount_atomic=1_000_001,
        success_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        months=3,
    )

    assert [entry.amount_atomic for entry in entries] == [333_334, 333_334, 333_333]
