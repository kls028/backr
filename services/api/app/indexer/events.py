from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CampaignEvent:
    event_type: str
    campaign: str
    supporter: str | None
    amount_atomic: int
    purchased_units: int
    immediate_units: int
    pending_units: int
    successful: bool | None = None
    creator: str | None = None
    usdc_mint: str | None = None
    snapshot_hash: bytes | None = None
