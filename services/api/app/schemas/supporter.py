from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class PurchaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purchased_units: int = Field(ge=1, le=1_000)
    source_token_account: str = Field(min_length=32, max_length=50)
    escrow_token_account: str = Field(min_length=32, max_length=50)


class PurchaseIntentOut(BaseModel):
    campaign_id: uuid.UUID
    purchased_units: int
    amount_atomic: int
    immediate_units: int
    pending_units: int
    confirmed_points: int
    pending_points: int
    transaction: str
    blockhash: str
    last_valid_block_height: int
    simulation_logs: list[str]


class SupportPointAccountOut(BaseModel):
    profile_id: uuid.UUID
    available_points: int
    pending_points: int
    updated_at: dt.datetime


class SupportPointLedgerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    operation_type: str
    delta_points: int
    available_balance_after: int
    pending_balance_after: int
    campaign_id: uuid.UUID | None
    contribution_id: uuid.UUID | None
    transaction_reference: str | None
    created_at: dt.datetime


class ContributionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    transaction_signature: str
    purchased_units: int
    contributed_amount_atomic: int
    immediate_units: int
    pending_units: int
    status: str
    base_points_confirmed: int
    base_points_pending: int
    success_bonus_points: int
    created_at: dt.datetime
