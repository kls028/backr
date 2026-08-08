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
import re
from typing import Any, cast

import structlog
from sqlalchemy import CursorResult
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CounterEvent

log = structlog.get_logger(__name__)

_PROGRAM_DATA_PREFIX = "Program data: "
_COUNTER_LOG = re.compile(r"Counter is now (\d+)")


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
