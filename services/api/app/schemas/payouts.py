from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class PayoutVestingEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contribution_id: uuid.UUID | None
    athlete_profile_id: uuid.UUID
    amount_atomic: int
    release_at: dt.datetime
    kind: str
    status: str
    transaction_signature: str | None
    created_at: dt.datetime
    released_at: dt.datetime | None
