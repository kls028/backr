"""Reconciliation worker.

Webhooks are at-least-once *at best*. Helius will drop deliveries during
incidents, and your own service will be down for deploys. This worker is the
safety net: it walks the program's signature history and fills in anything the
webhook path missed.

Runs as a separate container from the same image (see infra/docker-compose.yml).
It shares the codebase, not the process, so a wedged backfill cannot take the
API down with it.

Correctness rests on both write paths being idempotent -- ON CONFLICT DO NOTHING
in the ingest table and in every projection. Do not add a write that is not.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import signal
from typing import Any, cast

import httpx
import structlog
from sqlalchemy import CursorResult, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import dispose_engine, get_session_factory, init_engine
from app.indexer.parser import derive_events
from app.logging import configure_logging
from app.models import IndexedTransaction, IndexerCursor, IngestStatus
from app.solana.client import RpcError, SolanaRpc

log = structlog.get_logger(__name__)


async def _load_cursor(session: AsyncSession, program_id: str) -> IndexerCursor:
    cursor = await session.scalar(
        select(IndexerCursor).where(IndexerCursor.program_id == program_id)
    )
    if cursor is None:
        cursor = IndexerCursor(program_id=program_id)
        session.add(cursor)
        await session.flush()
    return cursor


async def _beat(settings: Settings) -> str | None:
    """Record that the worker is alive, in its own transaction.

    This is deliberately separate from the sweep. The heartbeat answers "is the
    worker container running and looping"; whether the RPC node is reachable is
    a different question, answered elsewhere. Committing it up front in its own
    transaction means an unreachable node cannot make a healthy worker look
    dead -- an earlier version stamped the heartbeat inside the sweep's
    transaction, so any RPC failure rolled it back along with everything else.

    Returns the cursor position to resume from.
    """
    async with get_session_factory()() as session:
        cursor = await _load_cursor(session, settings.program_id)
        cursor.last_run_at = dt.datetime.now(tz=dt.UTC)
        until = cursor.last_signature
        await session.commit()
        return until


async def run_once(rpc: SolanaRpc, settings: Settings) -> int:
    """One reconciliation sweep. Returns the number of transactions ingested."""
    until = await _beat(settings)
    session_factory = get_session_factory()

    async with session_factory() as session:
        cursor = await _load_cursor(session, settings.program_id)

        try:
            signatures = await rpc.get_signatures_for_address(
                settings.program_id,
                limit=settings.reconcile_batch_size,
                until=until,
            )
        except (RpcError, httpx.HTTPError) as exc:
            # Covers both a JSON-RPC error object and a transport failure. The
            # node being down or unreachable is expected during development --
            # the validator restarts constantly -- so log it and wait for the
            # next tick rather than treating it as a worker fault.
            log.warning("reconcile_signature_fetch_failed", error=str(exc))
            return 0

        if not signatures:
            await session.commit()
            return 0

        # getSignaturesForAddress returns newest first. Process oldest first so
        # an interrupted run leaves the cursor on a contiguous prefix rather
        # than skipping the gap underneath it.
        signatures.reverse()

        ingested = 0
        entries: list[dict[str, Any]] = []

        for item in signatures:
            signature = item.get("signature")
            if not isinstance(signature, str):
                continue

            transaction = await rpc.get_transaction(signature)
            if transaction is None:
                log.warning("reconcile_transaction_missing", signature=signature)
                continue

            entry = {**transaction, "signature": signature, "slot": item.get("slot") or 0}
            entries.append(entry)

            statement = (
                insert(IndexedTransaction)
                .values(
                    signature=signature,
                    slot=int(entry["slot"] or 0),
                    block_time=(
                        dt.datetime.fromtimestamp(float(entry["blockTime"]), tz=dt.UTC)
                        if entry.get("blockTime")
                        else None
                    ),
                    program_id=settings.program_id,
                    source="reconcile",
                    status=IngestStatus.pending,
                    raw=entry,
                )
                .on_conflict_do_nothing(index_elements=["signature"])
            )
            result = cast(CursorResult[Any], await session.execute(statement))
            ingested += result.rowcount or 0

            cursor.last_signature = signature
            cursor.last_slot = int(entry["slot"] or 0)

        derived = await derive_events(
            session, entries, settings.program_id, settings.usdc_mint or None
        )
        cursor.backfill_complete = True
        await session.commit()

        if ingested or derived:
            log.info("reconcile_sweep", ingested=ingested, derived=derived, scanned=len(signatures))

        return ingested


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.environment != "local")
    init_engine(settings)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)

    log.info("reconciler_started", interval=settings.reconcile_interval_seconds)
    rpc = SolanaRpc(settings.solana_rpc_url)

    try:
        while not stop.is_set():
            try:
                await run_once(rpc, settings)
            except Exception:
                log.exception("reconcile_sweep_failed")

            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=settings.reconcile_interval_seconds)
    finally:
        await rpc.aclose()
        await dispose_engine()
        log.info("reconciler_stopped")


if __name__ == "__main__":
    asyncio.run(main())
