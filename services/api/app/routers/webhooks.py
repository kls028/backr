"""Helius webhook ingest.

Helius POSTs an array of transactions and echoes back whatever string you set as
the webhook's auth header. That string is the only thing standing between this
endpoint and anyone on the internet writing rows into your database, so it is
compared in constant time and the route refuses to serve at all if it is unset.

Ingest is deliberately split from interpretation: we persist the raw payload,
return 200 fast so Helius stops retrying, and let the worker derive projections.
A slow parser must never turn into webhook back-pressure.
"""

from __future__ import annotations

import datetime as dt
import hmac
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy.dialects.postgresql import insert

from app.config import Settings
from app.db import SessionDep, SettingsDep
from app.indexer.parser import derive_events
from app.models import IndexedTransaction, IngestStatus

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = structlog.get_logger(__name__)


def _authorize(settings: Settings, provided: str | None) -> None:
    secret = settings.helius_webhook_secret
    if secret is None:
        # Fail closed. An unconfigured secret means an open write endpoint.
        log.error("helius_webhook_secret_unset")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook ingest is not configured",
        )

    if provided is None or not hmac.compare_digest(provided, secret.get_secret_value()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad webhook secret")


def _block_time(entry: dict[str, Any]) -> dt.datetime | None:
    timestamp = entry.get("timestamp") or entry.get("blockTime")
    if not isinstance(timestamp, int | float):
        return None
    return dt.datetime.fromtimestamp(float(timestamp), tz=dt.UTC)


@router.post("/helius", status_code=status.HTTP_202_ACCEPTED)
async def helius(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    _authorize(settings, authorization)

    payload = await request.json()
    entries: list[dict[str, Any]] = payload if isinstance(payload, list) else [payload]

    accepted = 0
    for entry in entries:
        signature = entry.get("signature")
        if not isinstance(signature, str) or not signature:
            log.warning("webhook_entry_without_signature")
            continue

        # ON CONFLICT DO NOTHING makes redelivery free. Helius retries on any
        # non-2xx, and at-least-once delivery is the normal case, not the edge.
        statement = (
            insert(IndexedTransaction)
            .values(
                signature=signature,
                slot=int(entry.get("slot") or 0),
                block_time=_block_time(entry),
                program_id=settings.program_id,
                source="webhook",
                status=IngestStatus.pending,
                raw=entry,
            )
            .on_conflict_do_nothing(index_elements=["signature"])
        )
        await session.execute(statement)
        accepted += 1

    # Derive projections inline for now -- volume is low and it keeps the read
    # model fresh. Move this to the worker when ingest gets hot.
    derived = await derive_events(
        session,
        entries,
        settings.program_id,
        settings.usdc_mint or None,
        settings.success_bonus_rate_bps,
    )

    log.info("helius_webhook_ingested", accepted=accepted, derived=derived)
    return {"accepted": accepted, "derived": derived}
