"""Payout vesting row creation.

Submission/release is intentionally kept separate from row creation. A worker
can claim due rows later without recomputing the source amount.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.payout import payout_vesting
from app.platform_models import PayoutVestingEntry


async def create_standard_vesting_entries(
    session: AsyncSession,
    contribution_id: uuid.UUID,
    athlete_profile_id: uuid.UUID,
    amount_atomic: int,
    success_at: dt.datetime,
    months: int = 12,
) -> list[PayoutVestingEntry]:
    """Persist an exact monthly schedule once for a successful contribution."""
    rows = [
        PayoutVestingEntry(
            contribution_id=contribution_id,
            athlete_profile_id=athlete_profile_id,
            amount_atomic=item.amount_atomic,
            release_at=item.release_at,
            kind="standard_monthly",
            status="scheduled",
        )
        for item in payout_vesting(amount_atomic, success_at, months)
    ]
    session.add_all(rows)
    await session.flush()
    return rows
