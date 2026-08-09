"""Cross-component diagnostics.

`/readyz` answers a yes/no question for an orchestrator. This answers a
different one, for a human: *which* hop is broken. Each check is isolated so one
failure does not mask the others, and every check reports the address it used --
"cannot reach the database" is much less useful than "cannot reach the database
at host.docker.internal:54422".

The checks deliberately span process boundaries:

  api      -> this container answered at all
  database -> api container reached the Supabase Postgres container
  supabase -> api container reached the Supabase Auth container
  rpc      -> api container reached the validator
  program  -> the program is actually deployed on that validator
  worker   -> the *worker* container is alive, via a heartbeat only it writes
  ingest   -> rows exist and are being drained

`worker` is the interesting one: the API has no direct link to the worker, so
the only evidence it is running is a row the worker updates on every sweep.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from solders.pubkey import Pubkey
from sqlalchemy import func, select, text

from app.db import SessionDep, SettingsDep
from app.models import IndexedTransaction, IndexerCursor, IngestStatus
from app.solana.client import SolanaRpc
from app.solana.tx import counter_pda

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])

Status = Literal["ok", "degraded", "error"]


class Check(BaseModel):
    name: str
    status: Status
    target: str = Field(description="What this check actually talked to")
    latency_ms: int | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class Diagnostics(BaseModel):
    status: Status
    environment: str
    checks: list[Check]


async def _timed(name: str, target: str, fn: Any) -> Check:
    """Run one check, catching everything. A failed probe must not 500 the page."""
    started = time.perf_counter()
    try:
        detail = await fn()
        return Check(
            name=name,
            status="ok",
            target=target,
            latency_ms=int((time.perf_counter() - started) * 1000),
            detail=detail or {},
        )
    except Exception as exc:  # noqa: BLE001 - the whole point is to report it
        return Check(
            name=name,
            status="error",
            target=target,
            latency_ms=int((time.perf_counter() - started) * 1000),
            error=f"{type(exc).__name__}: {exc}",
        )


async def get_rpc(settings: SettingsDep) -> Any:
    client = SolanaRpc(settings.solana_rpc_url, timeout=5.0)
    try:
        yield client
    finally:
        await client.aclose()


RpcDep = Annotated[SolanaRpc, Depends(get_rpc)]


@router.get("", response_model=Diagnostics)
async def diagnostics(session: SessionDep, settings: SettingsDep, rpc: RpcDep) -> Diagnostics:
    checks: list[Check] = [
        Check(
            name="api",
            status="ok",
            target="self",
            detail={"environment": settings.environment, "program_id": settings.program_id},
        )
    ]

    # --- database ----------------------------------------------------------
    async def database() -> dict[str, Any]:
        version = await session.scalar(text("select version()"))
        return {"server": str(version).split(",")[0]}

    checks.append(await _timed("database", _host(settings.database_url), database))

    # --- supabase auth -----------------------------------------------------
    async def supabase() -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.supabase_url.rstrip('/')}/auth/v1/health")
            response.raise_for_status()
            return {"health": response.json()}

    checks.append(await _timed("supabase", settings.supabase_url, supabase))

    # --- solana rpc --------------------------------------------------------
    async def solana() -> dict[str, Any]:
        version = await rpc.get_version()
        slot = await rpc.get_slot()
        return {"version": version.get("solana-core"), "slot": slot}

    checks.append(await _timed("solana_rpc", settings.solana_rpc_url, solana))

    # --- program deployed --------------------------------------------------
    async def program() -> dict[str, Any]:
        account = await rpc.get_account_info(settings.program_id)
        if account is None:
            raise RuntimeError("program account not found — is it deployed to this cluster?")
        pda, bump = counter_pda(Pubkey.from_string(settings.program_id))
        counter = await rpc.get_account_info(str(pda))
        return {
            "executable": bool(account.get("executable")),
            "owner": account.get("owner"),
            "counter_pda": str(pda),
            "counter_bump": bump,
            "counter_initialized": counter is not None,
        }

    checks.append(await _timed("program", settings.program_id, program))

    # --- worker heartbeat --------------------------------------------------
    async def worker() -> dict[str, Any]:
        cursor = await session.scalar(
            select(IndexerCursor).where(IndexerCursor.program_id == settings.program_id)
        )
        if cursor is None or cursor.last_run_at is None:
            raise RuntimeError("no heartbeat yet — worker container has not completed a sweep")

        age = (dt.datetime.now(tz=dt.UTC) - cursor.last_run_at).total_seconds()
        # Two missed intervals is the threshold: one can be a slow sweep.
        if age > settings.reconcile_interval_seconds * 2 + 15:
            raise RuntimeError(f"heartbeat is {int(age)}s old — worker may be stopped")

        return {
            "seconds_since_sweep": int(age),
            "last_slot": cursor.last_slot,
            "backfill_complete": cursor.backfill_complete,
        }

    checks.append(await _timed("worker", "indexer_cursors heartbeat", worker))

    # --- ingest backlog ----------------------------------------------------
    async def ingest() -> dict[str, Any]:
        total = await session.scalar(select(func.count()).select_from(IndexedTransaction)) or 0
        pending = (
            await session.scalar(
                select(func.count())
                .select_from(IndexedTransaction)
                .where(IndexedTransaction.status == IngestStatus.pending)
            )
            or 0
        )
        return {"total": int(total), "pending": int(pending)}

    checks.append(await _timed("ingest", "indexed_transactions", ingest))

    failed = [c for c in checks if c.status == "error"]
    overall: Status = "ok" if not failed else ("degraded" if len(failed) < 3 else "error")

    return Diagnostics(status=overall, environment=settings.environment, checks=checks)


def _host(url: str) -> str:
    """Strip credentials out of a DSN before showing it. Passwords are not diagnostics."""
    tail = url.rsplit("@", 1)[-1]
    return tail or "database"


class SimulatedIngest(BaseModel):
    signature: str
    derived: int
    counter: str
    authority: str
    count: int


@router.post("/simulate-ingest", response_model=SimulatedIngest)
async def simulate_ingest(session: SessionDep, settings: SettingsDep) -> SimulatedIngest:
    """Push a synthetic transaction through the real ingest path.

    This exercises write -> parse -> project -> read end to end from the browser
    without needing the webhook secret in frontend code or a public tunnel.

    Local only. In any deployed environment this would be a way to forge rows in
    the read model, so it refuses to exist there.
    """
    if settings.environment != "local":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not available outside local development",
        )

    # Imported here so the production import graph never pulls in a row forger.
    from app.indexer.parser import derive_events

    now = dt.datetime.now(tz=dt.UTC)
    signature = f"sim{int(now.timestamp() * 1000)}"
    pda, _ = counter_pda(Pubkey.from_string(settings.program_id))
    authority = "SiMuLaTeDAuThoRiTy11111111111111111111111111"

    current = await session.scalar(select(func.count()).select_from(IndexedTransaction)) or 0
    count = int(current) + 1

    entry: dict[str, Any] = {
        "signature": signature,
        "slot": int(now.timestamp()),
        "timestamp": int(now.timestamp()),
        "transaction": {"message": {"accountKeys": [authority, str(pda)]}},
        "meta": {"logMessages": [f"Program log: Hello, world! Counter is now {count}"]},
    }

    session.add(
        IndexedTransaction(
            signature=signature,
            slot=int(now.timestamp()),
            block_time=now,
            program_id=settings.program_id,
            source="simulated",
            status=IngestStatus.pending,
            raw=entry,
        )
    )
    await session.flush()

    derived = await derive_events(session, [entry], settings.program_id, settings.usdc_mint or None)

    return SimulatedIngest(
        signature=signature,
        derived=derived,
        counter=str(pda),
        authority=authority,
        count=count,
    )
