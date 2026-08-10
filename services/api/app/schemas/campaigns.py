from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.money import MoneyValidationError, parse_usdc_amount


def _validate_amount(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parse_usdc_amount(value)
    except MoneyValidationError as exc:
        raise ValueError(str(exc)) from exc
    return value.strip()


def _required_text(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} must not be empty")
    return normalized


class StretchGoalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_usdc: str = Field(min_length=1, max_length=40)
    benefit: str = Field(min_length=1, max_length=2_000)

    @field_validator("amount_usdc")
    @classmethod
    def validate_amount(cls, value: str) -> str:
        return _validate_amount(value) or value

    @field_validator("benefit")
    @classmethod
    def validate_benefit(cls, value: str) -> str:
        return _required_text(value, "benefit")


class RewardTierInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_units: int = Field(ge=1, le=1_000_000)
    benefit: str = Field(min_length=1, max_length=2_000)
    is_cumulative: bool = True
    max_supply: int | None = Field(default=None, ge=1, le=1_000_000_000)
    max_per_supporter: int | None = Field(default=None, ge=1, le=1_000_000_000)
    uri: str | None = Field(default=None, max_length=500)

    @field_validator("benefit")
    @classmethod
    def validate_benefit(cls, value: str) -> str:
        return _required_text(value, "benefit")

    @field_validator("uri")
    @classmethod
    def normalize_uri(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class CampaignCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: UUID
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=10_000)
    start_at: datetime
    end_at: datetime
    minimum_success_threshold_usdc: str = Field(min_length=1, max_length=40)
    main_goal_usdc: str | None = Field(default=None, max_length=40)
    stretch_goals: list[StretchGoalInput] = Field(default_factory=list, max_length=8)
    reward_tiers: list[RewardTierInput] = Field(default_factory=list, max_length=32)
    metadata_uri: str | None = Field(default=None, max_length=200)

    @field_validator("minimum_success_threshold_usdc", "main_goal_usdc")
    @classmethod
    def validate_amounts(cls, value: str | None) -> str | None:
        return _validate_amount(value)

    @field_validator("title", "description")
    @classmethod
    def normalize_required_text(cls, value: str, info: object) -> str:
        return _required_text(value, "campaign text")

    @field_validator("metadata_uri")
    @classmethod
    def normalize_metadata_uri(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def validate_dates(self) -> CampaignCreate:
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("start_at and end_at must include a timezone")
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class CampaignPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    escrow_token_account: str = Field(min_length=32, max_length=50)


class CampaignUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=10_000)
    start_at: datetime
    end_at: datetime
    minimum_success_threshold_usdc: str = Field(min_length=1, max_length=40)
    main_goal_usdc: str | None = Field(default=None, max_length=40)
    stretch_goals: list[StretchGoalInput] = Field(default_factory=list, max_length=8)
    reward_tiers: list[RewardTierInput] = Field(default_factory=list, max_length=32)
    metadata_uri: str | None = Field(default=None, max_length=200)

    @field_validator("minimum_success_threshold_usdc", "main_goal_usdc")
    @classmethod
    def validate_amounts(cls, value: str | None) -> str | None:
        return _validate_amount(value)

    @field_validator("title", "description")
    @classmethod
    def normalize_required_text(cls, value: str, info: object) -> str:
        return _required_text(value, "campaign text")

    @field_validator("metadata_uri")
    @classmethod
    def normalize_metadata_uri(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def validate_dates(self) -> CampaignUpdate:
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("start_at and end_at must include a timezone")
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    athlete_profile_id: UUID
    athlete_display_name: str | None = None
    athlete_sport: str | None = None
    athlete_bio: str | None = None
    plan_id: UUID
    title: str
    description: str
    unit_price_usdc: str
    unit_price_usdc_atomic: int
    minimum_success_threshold_usdc: str
    minimum_success_threshold_atomic: int
    main_goal_usdc: str | None
    main_goal_atomic: int | None
    start_at: datetime
    end_at: datetime
    metadata_uri: str | None
    metadata_hash: str | None
    status: str
    campaign_pda: str | None
    escrow_token_account: str | None
    chain_signature: str | None
    publish_confirmation_status: str | None = None
    stretch_goals: list[dict[str, object]]
    reward_tiers: list[dict[str, object]]
    created_at: datetime
    updated_at: datetime


class CampaignPublishOut(BaseModel):
    campaign_id: UUID
    publish_intent_id: UUID
    campaign_pda: str
    snapshot_hash: str
    transaction: str
    blockhash: str
    last_valid_block_height: int
    simulation_logs: list[str]


class CampaignPublishConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signature: str = Field(min_length=32, max_length=100)
    campaign_pda: str = Field(min_length=32, max_length=50)


class CampaignPublishConfirmOut(BaseModel):
    campaign_id: UUID
    publish_intent_id: UUID
    signature: str
    status: str
    confirmed_at: datetime


class SettlementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    successful: bool
    supporter_wallet: str = Field(min_length=32, max_length=50)
    supporter_token_account: str = Field(min_length=32, max_length=50)
    escrow_token_account: str = Field(min_length=32, max_length=50)


class SettlementIntentOut(BaseModel):
    campaign_id: UUID
    successful: bool
    transaction: str
    blockhash: str
    last_valid_block_height: int
    simulation_logs: list[str]
