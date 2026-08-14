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
import json
import re
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

import structlog
from solders.pubkey import Pubkey
from sqlalchemy import CursorResult, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.campaigns import public_campaign_status
from app.indexer.events import CampaignEvent
from app.indexer.settlement import project_purchase_event, project_settlement_event
from app.models import CampaignChainEvent, CounterEvent, IndexedTransaction, IngestStatus
from app.platform_models import Campaign, CampaignPublishIntent
from app.solana.campaign import (
    CampaignInitializationArgs,
    campaign_pda,
    decode_initialize_campaign_data,
)

log = structlog.get_logger(__name__)

_PROGRAM_DATA_PREFIX = "Program data: "
_COUNTER_LOG = re.compile(r"Counter is now (\d+)")


class IndexerParseError(ValueError):
    """A transaction cannot be trusted as a campaign publication."""


@dataclass(frozen=True, slots=True)
class ParsedCampaignInitialization:
    signature: str
    program_id: str
    creator: str
    campaign_pda: str
    usdc_mint: str
    escrow_token_account: str
    system_program: str
    args: CampaignInitializationArgs

    @property
    def unit_price_atomic(self) -> int:
        return self.args.unit_price_atomic

    @property
    def metadata_hash(self) -> bytes:
        return self.args.metadata_hash


_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _decode_base58(value: str) -> bytes:
    if not value:
        return b""
    number = 0
    for character in value:
        try:
            number = number * 58 + _BASE58_ALPHABET.index(character)
        except ValueError as exc:
            raise IndexerParseError("instruction data is not valid base58") from exc
    decoded = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return b"\0" * (len(value) - len(value.lstrip("1"))) + decoded


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
                    creator=_pubkey_text(payload[40:72]),
                    usdc_mint=_pubkey_text(payload[72:104]),
                    snapshot_hash=payload[104:136],
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


def _instruction_records(entry: dict[str, Any]) -> list[tuple[str, list[str], bytes]]:
    transaction = entry.get("transaction") or {}
    message = transaction.get("message") or {}
    keys = _account_keys(entry)
    instructions = message.get("instructions")
    if not isinstance(instructions, list):
        return []

    records: list[tuple[str, list[str], bytes]] = []
    for raw in instructions:
        if not isinstance(raw, dict):
            continue
        program_id = raw.get("programId")
        if not isinstance(program_id, str):
            program_index = raw.get("programIdIndex")
            program_id = (
                keys[program_index]
                if isinstance(program_index, int) and program_index < len(keys)
                else ""
            )
        raw_accounts = raw.get("accounts")
        accounts: list[str] = []
        if isinstance(raw_accounts, list):
            for account in raw_accounts:
                if isinstance(account, int) and account < len(keys):
                    accounts.append(keys[account])
                elif isinstance(account, str):
                    accounts.append(account)
        encoded_data = raw.get("data")
        if not isinstance(encoded_data, str):
            continue
        records.append((program_id, accounts, _decode_base58(encoded_data)))
    return records


def _signer_keys(entry: dict[str, Any]) -> set[str] | None:
    message = (entry.get("transaction") or {}).get("message") or {}
    keys = message.get("accountKeys")
    if not isinstance(keys, list) or not keys or not isinstance(keys[0], dict):
        return None
    return {
        str(item.get("pubkey"))
        for item in keys
        if isinstance(item, dict) and item.get("signer") is True
    }


def parse_campaign_initialization(
    raw_transaction: dict[str, Any], expected_program_id: str
) -> ParsedCampaignInitialization:
    """Parse exactly one initialize-campaign instruction from a raw RPC entry."""
    if (raw_transaction.get("meta") or {}).get("err") is not None:
        raise IndexerParseError("publication transaction failed on-chain")
    records = _instruction_records(raw_transaction)
    expected_records = [record for record in records if record[0] == expected_program_id]
    if not expected_records:
        raise IndexerParseError("unexpected program in publication transaction")

    for program_id, accounts, data in expected_records:
        try:
            args = decode_initialize_campaign_data(data)
        except (ValueError, UnicodeDecodeError):
            continue
        if len(accounts) < 5:
            raise IndexerParseError("campaign initialization has incomplete accounts")
        creator, campaign, usdc_mint, escrow, system_program = accounts[:5]
        signers = _signer_keys(raw_transaction)
        if signers is not None and creator not in signers:
            raise IndexerParseError("creator signer is missing")
        try:
            creator_key = Pubkey.from_string(creator)
            expected_campaign, _ = campaign_pda(
                Pubkey.from_string(expected_program_id),
                creator_key,
                args.nonce,
            )
        except ValueError as exc:
            raise IndexerParseError("campaign initialization contains an invalid account") from exc
        if campaign != str(expected_campaign):
            raise IndexerParseError("campaign PDA does not match creator and nonce")
        return ParsedCampaignInitialization(
            signature=str(raw_transaction.get("signature") or ""),
            program_id=program_id,
            creator=creator,
            campaign_pda=campaign,
            usdc_mint=usdc_mint,
            escrow_token_account=escrow,
            system_program=system_program,
            args=args,
        )

    raise IndexerParseError("initialize_campaign instruction not found")


def _snapshot_datetime(value: object, field: str) -> int:
    if not isinstance(value, str):
        raise IndexerParseError(f"snapshot {field} is invalid")
    try:
        timestamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IndexerParseError(f"snapshot {field} is invalid") from exc
    if timestamp.tzinfo is None:
        raise IndexerParseError(f"snapshot {field} is missing timezone")
    return int(timestamp.timestamp())


def verify_campaign_publish(
    intent: CampaignPublishIntent,
    campaign: Campaign,
    parsed: ParsedCampaignInitialization,
    expected_usdc_mint: str,
) -> None:
    """Compare a parsed chain transaction with the immutable publish snapshot."""
    if not intent.confirmation_signature:
        raise IndexerParseError("publication signature has not been submitted")
    if parsed.signature != intent.confirmation_signature:
        raise IndexerParseError("publication signature does not match intent")
    if parsed.campaign_pda != intent.campaign_pda:
        raise IndexerParseError("campaign PDA does not match intent")
    if parsed.usdc_mint != expected_usdc_mint:
        raise IndexerParseError("publication uses an unexpected USDC mint")
    if not isinstance(campaign.publish_snapshot, Mapping):
        raise IndexerParseError("campaign publication snapshot is missing")

    raw_snapshot = campaign.publish_snapshot.get("snapshot")
    if isinstance(raw_snapshot, str):
        try:
            snapshot = json.loads(raw_snapshot)
        except json.JSONDecodeError as exc:
            raise IndexerParseError("campaign publication snapshot is invalid") from exc
    else:
        snapshot = raw_snapshot
    if not isinstance(snapshot, Mapping):
        raise IndexerParseError("campaign publication snapshot is invalid")
    if snapshot.get("campaign_id") != str(campaign.id):
        raise IndexerParseError("publication snapshot campaign does not match row")
    terms = snapshot.get("terms")
    if not isinstance(terms, Mapping):
        raise IndexerParseError("publication snapshot terms are missing")
    try:
        nonce = bytes.fromhex(str(snapshot["nonce"]))
        expected_escrow = str(Pubkey.from_string(str(terms["escrow_token_account"])))
        expected_args = CampaignInitializationArgs(
            nonce=nonce,
            unit_price_atomic=int(terms["unit_price_atomic"]),
            minimum_success_threshold_atomic=int(terms["minimum_success_threshold_atomic"]),
            main_goal_atomic=int(terms["main_goal_atomic"]),
            stretch_goals_atomic=[int(goal) for goal in terms["stretch_goals_atomic"]],
            start_at=_snapshot_datetime(terms["start_at"], "start_at"),
            end_at=_snapshot_datetime(terms["end_at"], "end_at"),
            metadata_uri=str(terms.get("metadata_uri") or ""),
            metadata_hash=bytes(intent.snapshot_hash),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise IndexerParseError("publication snapshot terms are invalid") from exc
    if len(nonce) != 16 or intent.nonce != nonce:
        raise IndexerParseError("publication nonce does not match intent")
    if expected_escrow != parsed.escrow_token_account:
        raise IndexerParseError("escrow account does not match publication snapshot")
    if parsed.args != expected_args:
        raise IndexerParseError("campaign initialization terms do not match snapshot")


def _block_time(entry: dict[str, Any]) -> dt.datetime | None:
    timestamp = entry.get("timestamp") or entry.get("blockTime")
    if not isinstance(timestamp, int | float):
        return None
    return dt.datetime.fromtimestamp(float(timestamp), tz=dt.UTC)


async def derive_events(
    session: AsyncSession,
    entries: list[dict[str, Any]],
    program_id: str,
    expected_usdc_mint: str | None = None,
    bonus_rate_bps: int = 2_000,
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
        indexed = await session.scalar(
            select(IndexedTransaction).where(IndexedTransaction.signature == signature)
        )

        logs = _logs(entry)
        decoded_events = decode_campaign_events(decode_program_data(logs))
        for event_index, event in enumerate(decoded_events):
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
            await project_settlement_event(session, event, signature, bonus_rate_bps)

            if event.event_type == "campaign_initialized":
                if expected_usdc_mint is None:
                    if indexed is not None:
                        indexed.status = IngestStatus.skipped
                        indexed.error = "USDC mint is not configured for publication verification"
                    log.warning("campaign_publication_verification_skipped", signature=signature)
                    continue
                try:
                    parsed = parse_campaign_initialization(entry, program_id)
                    intent = await session.scalar(
                        select(CampaignPublishIntent).where(
                            CampaignPublishIntent.campaign_pda == parsed.campaign_pda
                        )
                    )
                    campaign = (
                        await session.get(Campaign, intent.campaign_id)
                        if intent is not None
                        else None
                    )
                    if intent is None or campaign is None:
                        raise IndexerParseError("campaign publication intent was not found")
                    verify_campaign_publish(intent, campaign, parsed, expected_usdc_mint)
                    intent.confirmation_status = "verified"
                    intent.confirmation_error = None
                    campaign.chain_signature = signature
                    campaign.status = public_campaign_status(campaign.start_at, _block_time(entry))
                    if indexed is not None:
                        indexed.status = IngestStatus.processed
                        indexed.error = None
                except (IndexerParseError, ValueError) as exc:
                    if indexed is not None:
                        indexed.status = IngestStatus.failed
                        indexed.error = str(exc)
                    log.warning(
                        "campaign_publication_verification_failed",
                        signature=signature,
                        error=str(exc),
                    )

        match = _COUNTER_LOG.search("\n".join(logs))
        if match is None:
            if indexed is not None and indexed.status == IngestStatus.pending:
                indexed.status = IngestStatus.processed
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
        if indexed is not None and indexed.status == IngestStatus.pending:
            indexed.status = IngestStatus.processed

    return written
