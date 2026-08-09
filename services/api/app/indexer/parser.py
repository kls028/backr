"""Turning raw transactions into projection rows.

Two ways to read state out of a Solana transaction:

  1. `msg!` log lines. Easy, and what the starter program does, but the format is
     whatever a human typed -- it breaks the moment someone edits the string.
  2. Anchor `emit!` events, which land in the logs as `Program data: <base64>`
     prefixed by an 8-byte event discriminator. Stable, versioned, decodable.

Use (2) for anything you care about. `decode_program_data` below is the hook for
it. The counter parser uses (1) only because the template program has no events
yet -- replace it when you add `emit!`.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import re
import struct
from typing import Any, cast

import structlog
from sqlalchemy import CursorResult
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.indexer.events import CampaignEvent
from app.indexer.settlement import project_purchase_event, project_settlement_event
from app.models import CampaignChainEvent, CounterEvent

log = structlog.get_logger(__name__)

_PROGRAM_DATA_PREFIX = "Program data: "
_COUNTER_LOG = re.compile(r"Counter is now (\d+)")


def _discriminator(name: str) -> bytes:
    return hashlib.sha256(f"event:{name}".encode()).digest()[:8]


def _pubkey_text(value: bytes) -> str:
    from solders.pubkey import Pubkey

    return str(Pubkey.from_bytes(value))


def decode_campaign_events(payloads: list[bytes]) -> list[CampaignEvent]:
    """Decode the stable Anchor events emitted by the campaign instructions."""
    events: list[CampaignEvent] = []
    purchase_disc = _discriminator("SubscriptionPurchased")
    initialized_disc = _discriminator("CampaignInitialized")
    settled_disc = _discriminator("CampaignSettled")
    for payload in payloads:
        if payload.startswith(purchase_disc) and len(payload) == 8 + 32 + 32 + 32:
            campaign = _pubkey_text(payload[8:40])
            supporter = _pubkey_text(payload[40:72])
            amount, purchased, immediate, pending = struct.unpack("<QQQQ", payload[72:])
            events.append(
                CampaignEvent(
                    "subscription_purchased",
                    campaign,
                    supporter,
                    amount,
                    purchased,
                    immediate,
                    pending,
                )
            )
        elif payload.startswith(initialized_disc) and len(payload) == 8 + 32 + 32 + 32 + 32:
            events.append(
                CampaignEvent(
                    "campaign_initialized",
                    _pubkey_text(payload[8:40]),
                    None,
                    0,
                    0,
                    0,
                    0,
                )
            )
        elif payload.startswith(settled_disc) and len(payload) == 8 + 32 + 32 + 1 + 8:
            campaign = _pubkey_text(payload[8:40])
            supporter = _pubkey_text(payload[40:72])
            successful = payload[72] == 1
            (pending_units,) = struct.unpack("<Q", payload[73:])
            events.append(
                CampaignEvent(
                    "campaign_settled",
                    campaign,
                    supporter,
                    0,
                    0,
                    0,
                    pending_units,
                    successful,
                )
            )
    return events


def decode_program_data(logs: list[str]) -> list[bytes]:
    """Extract every `emit!`ed event payload from a transaction's logs.

    Each returned blob starts with the 8-byte event discriminator
    (sha256("event:<EventName>")[:8]), followed by Borsh-encoded fields.
    """
    payloads: list[bytes] = []
    for line in logs:
        if not line.startswith(_PROGRAM_DATA_PREFIX):
            continue
        encoded = line[len(_PROGRAM_DATA_PREFIX) :].strip()
        try:
            # binascii.Error subclasses ValueError, so this covers both the
            # padding and the alphabet failure modes.
            payloads.append(base64.b64decode(encoded, validate=True))
        except ValueError:
            log.warning("undecodable_program_data", line=line[:120])
    return payloads


def _logs(entry: dict[str, Any]) -> list[str]:
    """Helius enhanced payloads and raw getTransaction results nest logs differently."""
    meta = entry.get("meta") or {}
    for candidate in (entry.get("logs"), meta.get("logMessages")):
        if isinstance(candidate, list):
            return [line for line in candidate if isinstance(line, str)]
    return []


def _account_keys(entry: dict[str, Any]) -> list[str]:
    transaction = entry.get("transaction") or {}
    message = transaction.get("message") or {}
    keys = message.get("accountKeys")

    if isinstance(keys, list):
        return [key if isinstance(key, str) else str(key.get("pubkey", "")) for key in keys]

    # Helius enhanced format
    accounts = entry.get("accountData")
    if isinstance(accounts, list):
        return [str(item.get("account", "")) for item in accounts]

    return []


def _block_time(entry: dict[str, Any]) -> dt.datetime | None:
    timestamp = entry.get("timestamp") or entry.get("blockTime")
    if not isinstance(timestamp, int | float):
        return None
    return dt.datetime.fromtimestamp(float(timestamp), tz=dt.UTC)


async def derive_events(
    session: AsyncSession,
    entries: list[dict[str, Any]],
    program_id: str,
) -> int:
    """Write projection rows for the transactions we understand.

    Idempotent: the unique (signature, counter) constraint plus DO NOTHING means
    replaying the same transaction is a no-op, which is what makes reconciliation
    safe to run on top of live webhook traffic.
    """
    written = 0

    for entry in entries:
        signature = entry.get("signature")
        if not isinstance(signature, str) or not signature:
            continue

        logs = _logs(entry)
        for event_index, event in enumerate(decode_campaign_events(decode_program_data(logs))):
            event_statement = (
                insert(CampaignChainEvent)
                .values(
                    signature=signature,
                    event_index=event_index,
                    event_type=event.event_type,
                    campaign=event.campaign,
                    supporter=event.supporter,
                    amount_atomic=event.amount_atomic,
                    purchased_units=event.purchased_units,
                    immediate_units=event.immediate_units,
                    pending_units=event.pending_units,
                    successful=event.successful,
                    slot=int(entry.get("slot") or 0),
                    block_time=_block_time(entry),
                )
                .on_conflict_do_nothing(index_elements=["signature", "event_index"])
            )
            event_result = cast(CursorResult[Any], await session.execute(event_statement))
            written += event_result.rowcount or 0
            await project_purchase_event(session, event, signature)
            await project_settlement_event(session, event, signature)

        match = _COUNTER_LOG.search("\n".join(logs))
        if match is None:
            continue

        keys = _account_keys(entry)
        # Fee payer signs and pays; for both counter instructions that is the
        # authority. Adjust if you add instructions where that stops holding.
        authority = keys[0] if keys else ""
        counter = next((key for key in keys[1:] if key and key != program_id), "")

        if not authority or not counter:
            log.warning("counter_event_missing_accounts", signature=signature)
            continue

        statement = (
            insert(CounterEvent)
            .values(
                signature=signature,
                counter=counter,
                authority=authority,
                count=int(match.group(1)),
                slot=int(entry.get("slot") or 0),
                block_time=_block_time(entry),
            )
            .on_conflict_do_nothing(index_elements=["signature", "counter"])
        )
        # rowcount is 0 when the ON CONFLICT clause suppressed the insert, which
        # is exactly how we count genuinely-new rows during a replay.
        result = cast(CursorResult[Any], await session.execute(statement))
        written += result.rowcount or 0

    return written
