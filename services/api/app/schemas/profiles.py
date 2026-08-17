from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class AthleteProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=80)
    sport: str | None = Field(default=None, max_length=80)
    bio: str | None = Field(default=None, max_length=2_000)
    avatar_uri: str | None = Field(default=None, max_length=500)


class AthleteProfileOut(AthleteProfileUpdate):
    # from_attributes is required to build this from the SQLAlchemy row, and the
    # ids must be UUID rather than str: pydantic v2 does not coerce UUID -> str,
    # so declaring them as str made every successful activation return a 500
    # ResponseValidationError *after* the row was written. JSON output is
    # unchanged — a UUID still serialises to its string form.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_id: uuid.UUID
