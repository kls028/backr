from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AthleteProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=80)
    sport: str | None = Field(default=None, max_length=80)
    bio: str | None = Field(default=None, max_length=2_000)
    avatar_uri: str | None = Field(default=None, max_length=500)


class AthleteProfileOut(AthleteProfileUpdate):
    id: str
    profile_id: str
