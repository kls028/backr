"""Read APIs over the indexed data.

These are the queries RPC cannot serve cheaply: ordered history, filtering by
authority, pagination. Anything that needs to be trustworthy at the moment of
use should still be read from chain by the client.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.db import SessionDep
from app.models import CounterEvent

router = APIRouter(prefix="/events", tags=["events"])


class CounterEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    signature: str
    counter: str
    authority: str
    count: int
    slot: int
    block_time: dt.datetime | None


@router.get("/counter", response_model=list[CounterEventOut])
async def list_counter_events(
    session: SessionDep,
    authority: Annotated[str | None, Query(max_length=44)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before_slot: Annotated[int | None, Query(ge=0)] = None,
) -> list[CounterEvent]:
    statement = select(CounterEvent).order_by(CounterEvent.slot.desc()).limit(limit)

    if authority:
        statement = statement.where(CounterEvent.authority == authority)
    if before_slot is not None:
        # Keyset pagination. OFFSET degrades badly once the table grows.
        statement = statement.where(CounterEvent.slot < before_slot)

    result = await session.execute(statement)
    return list(result.scalars().all())
