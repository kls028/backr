"""Athlete payout and vesting read APIs."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.auth import CurrentUserDep
from app.db import SessionDep
from app.platform_models import PayoutVestingEntry
from app.routers.plans import _athlete
from app.schemas.payouts import PayoutVestingEntryOut

router = APIRouter(prefix="/athlete/payouts", tags=["payouts"])


@router.get("", response_model=list[PayoutVestingEntryOut])
async def list_payouts(
    user: CurrentUserDep, session: SessionDep, limit: int = 100
) -> list[PayoutVestingEntryOut]:
    athlete = await _athlete(user, session)
    rows = list(
        await session.scalars(
            select(PayoutVestingEntry)
            .where(PayoutVestingEntry.athlete_profile_id == athlete.id)
            .order_by(PayoutVestingEntry.release_at, PayoutVestingEntry.id)
            .limit(min(max(limit, 1), 500))
        )
    )
    return [PayoutVestingEntryOut.model_validate(row) for row in rows]
