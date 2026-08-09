"""Fee and athlete payout calculations."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from app.domain.settlement import SettlementValidationError, vesting_schedule


@dataclass(frozen=True, slots=True)
class PayoutEntry:
    amount_atomic: int
    release_at: dt.datetime
    kind: str


def calculate_platform_fee(amount_atomic: int, fee_bps: int) -> int:
    if not isinstance(amount_atomic, int) or amount_atomic < 0:
        raise SettlementValidationError("amount_atomic must be non-negative")
    if not isinstance(fee_bps, int) or not 0 <= fee_bps <= 10_000:
        raise SettlementValidationError("fee_bps must be between 0 and 10000")
    return amount_atomic * fee_bps // 10_000


def payout_vesting(
    amount_atomic: int,
    success_at: dt.datetime,
    months: int = 12,
) -> list[PayoutEntry]:
    return [
        PayoutEntry(item.amount_atomic, item.release_at, "athlete_payout")
        for item in vesting_schedule(amount_atomic, success_at, months, "standard_monthly")
    ]
