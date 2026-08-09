from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class CosmeticItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    support_points_price: int
    metadata_uri: str | None
    available_quantity: int | None


class CosmeticOrderOut(BaseModel):
    id: uuid.UUID
    cosmetic_item_id: uuid.UUID
    points_spent: int
    available_points_after: int
    acquired_at: dt.datetime


class AthleteRewardOfferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reward_name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2_000)
    support_points_price: int = Field(ge=1, le=1_000_000_000)
    available_quantity: int | None = Field(default=None, ge=0)
    maximum_per_user: int | None = Field(default=None, ge=1)
    availability_start: dt.datetime | None = None
    availability_end: dt.datetime | None = None
    fulfillment_type: str = Field(default="digital", pattern="^(digital|physical|session)$")
    metadata_uri: str | None = Field(default=None, max_length=500)


class AthleteRewardOfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    athlete_profile_id: uuid.UUID
    reward_name: str
    description: str
    support_points_price: int
    available_quantity: int | None
    maximum_per_user: int | None
    availability_start: dt.datetime | None
    availability_end: dt.datetime | None
    fulfillment_type: str
    metadata_uri: str | None
    status: str


class AthleteRewardOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    offer_id: uuid.UUID
    points_spent: int
    status: str
    fulfillment_details: dict[str, object] | None
    created_at: dt.datetime
