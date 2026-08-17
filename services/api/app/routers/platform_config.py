"""Public platform configuration.

The browser needs a few chain constants to build requests: the program id, the
USDC mint (to derive the buyer's own associated token account), and the point
rates so a checkout summary can be shown before any network round-trip.

Serving them from the API rather than duplicating them as VITE_ variables keeps
one source of truth — a frontend built against a different mint than the backend
expects fails in confusing ways at signature time.

Everything here is public by design: program ids and mints are on-chain facts.
No secret may be added to this response.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.db import SettingsDep
from app.domain.settlement import BASE_POINTS_PER_UNIT

router = APIRouter(prefix="/config", tags=["config"])


class PlatformConfigOut(BaseModel):
    program_id: str
    usdc_mint: str
    usdc_decimals: int
    base_points_per_unit: int
    success_bonus_rate_bps: int
    max_active_units: int
    configured: bool


@router.get("", response_model=PlatformConfigOut)
async def read_config(settings: SettingsDep) -> PlatformConfigOut:
    return PlatformConfigOut(
        program_id=settings.program_id,
        usdc_mint=settings.usdc_mint,
        usdc_decimals=6,
        base_points_per_unit=BASE_POINTS_PER_UNIT,
        success_bonus_rate_bps=settings.success_bonus_rate_bps,
        # Spec §80: the forward active-subscription limit, in months.
        max_active_units=12,
        # Lets the UI say "purchases are unavailable" precisely instead of
        # surfacing a 503 from the purchase route after the user picks units.
        configured=bool(settings.usdc_mint and settings.program_id),
    )
