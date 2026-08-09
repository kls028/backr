from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.money import MoneyValidationError, parse_usdc_amount


class SubscriptionPlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_price_usdc: str = Field(min_length=1, max_length=40)
    benefits: str = Field(min_length=1, max_length=4_000)

    @field_validator("unit_price_usdc")
    @classmethod
    def validate_price(cls, value: str) -> str:
        try:
            parse_usdc_amount(value)
        except MoneyValidationError as exc:
            raise ValueError(str(exc)) from exc
        return value.strip()


class SubscriptionPlanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benefits: str = Field(min_length=1, max_length=4_000)


class SubscriptionPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    athlete_profile_id: UUID
    unit_price_usdc: str
    unit_price_usdc_atomic: int
    benefits: str
    status: str
    created_at: datetime
    updated_at: datetime
