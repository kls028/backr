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


class OwnedCosmeticOut(BaseModel):
    id: uuid.UUID
    cosmetic_item_id: uuid.UUID
    name: str
    description: str
    metadata_uri: str | None
    acquired_at: dt.datetime


class RedeemRequest(BaseModel):
    """Optional replay guard for a redemption.

    A repeated call carrying the same key returns the original order instead of
    reserving a second one. Omitting it preserves the pre-Part-3 behaviour.
    """

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)


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


class AthleteRewardOfferUpdate(BaseModel):
    """Partial update. Only the supplied fields are written."""

    model_config = ConfigDict(extra="forbid")

    reward_name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=2_000)
    support_points_price: int | None = Field(default=None, ge=1, le=1_000_000_000)
    available_quantity: int | None = Field(default=None, ge=0)
    maximum_per_user: int | None = Field(default=None, ge=1)
    availability_start: dt.datetime | None = None
    availability_end: dt.datetime | None = None
    metadata_uri: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, pattern="^(draft|active|archived)$")


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


# ---------------------------------------------------------------------------
# Fulfillment details
# ---------------------------------------------------------------------------
# Each fulfillment type collects only what its delivery actually needs. Free-form
# JSON would let a physical address leak into a digital reward's record.


class DigitalFulfillmentDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery_handle: str = Field(min_length=1, max_length=200)


class PhysicalFulfillmentDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_name: str = Field(min_length=1, max_length=120)
    address_line1: str = Field(min_length=1, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    postal_code: str = Field(min_length=1, max_length=32)
    country: str = Field(min_length=2, max_length=56)


class SessionFulfillmentDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred_times: str = Field(min_length=1, max_length=500)
    contact_handle: str = Field(min_length=1, max_length=200)


FULFILLMENT_DETAIL_MODELS: dict[str, type[BaseModel]] = {
    "digital": DigitalFulfillmentDetails,
    "physical": PhysicalFulfillmentDetails,
    "session": SessionFulfillmentDetails,
}


class FulfillmentDetailsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    details: dict[str, object]


class RewardOrderTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(min_length=1, max_length=40)
    fulfillment_reference: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=1_000)


class EntitlementTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(min_length=1, max_length=40)
    fulfillment_reference: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=1_000)


class SupporterRewardOrderOut(BaseModel):
    id: uuid.UUID
    offer_id: uuid.UUID
    offer_name: str
    athlete_display_name: str | None
    fulfillment_type: str
    points_spent: int
    status: str
    fulfillment_details: dict[str, object] | None
    created_at: dt.datetime
    updated_at: dt.datetime


class AthleteRewardOrderQueueOut(BaseModel):
    id: uuid.UUID
    offer_id: uuid.UUID
    offer_name: str
    fulfillment_type: str
    supporter_profile_id: uuid.UUID
    supporter_display_name: str | None
    points_spent: int
    status: str
    fulfillment_details: dict[str, object] | None
    allowed_transitions: list[str]
    created_at: dt.datetime
    updated_at: dt.datetime


class EntitlementOut(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    campaign_title: str
    reward_tier_id: uuid.UUID
    required_units: int
    benefit: str
    fulfillment_type: str
    status: str
    allowed_transitions: list[str]
    supporter_profile_id: uuid.UUID
    supporter_display_name: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


# ---------------------------------------------------------------------------
# Campaign reward view
# ---------------------------------------------------------------------------


class CampaignRewardTierOut(BaseModel):
    id: uuid.UUID
    position: int
    required_units: int
    benefit: str
    is_cumulative: bool
    reward_group: str | None
    uri: str | None
    max_supply: int | None
    supply_remaining: int | None
    unlocked_for_viewer: bool
    superseded_for_viewer: bool
    unlocked_but_unavailable: bool


class ViewerRewardState(BaseModel):
    confirmed_units: int
    pending_units: int
    entitlement_ids: list[uuid.UUID]


class CampaignRewardsOut(BaseModel):
    campaign_id: uuid.UUID
    tiers: list[CampaignRewardTierOut]
    viewer: ViewerRewardState | None
