"""Transaction-building endpoints.

Each route returns a base64 unsigned transaction. The browser deserialises it,
asks the wallet to sign, and submits it to an RPC node itself. The backend is
never in the custody path.

Every transaction is simulated before it is returned, so the user gets a useful
error instead of a wallet popup that fails on-chain.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from solders.pubkey import Pubkey

from app.auth import CurrentUserDep
from app.db import SettingsDep
from app.solana.client import RpcError, SolanaRpc
from app.solana.tx import (
    build_increment_ix,
    build_initialize_ix,
    counter_pda,
    to_unsigned_transaction,
)

router = APIRouter(prefix="/tx", tags=["transactions"])


class UnsignedTransaction(BaseModel):
    transaction: str = Field(description="base64-encoded unsigned v0 transaction")
    blockhash: str
    last_valid_block_height: int
    simulation_logs: list[str] = Field(default_factory=list)


async def get_rpc(settings: SettingsDep) -> Any:
    client = SolanaRpc(settings.solana_rpc_url)
    try:
        yield client
    finally:
        await client.aclose()


RpcDep = Annotated[SolanaRpc, Depends(get_rpc)]


def _parse_wallet(value: str | None) -> Pubkey:
    if not value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No wallet address on this session",
        )
    try:
        return Pubkey.from_string(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed wallet address",
        ) from exc


async def _compile(
    rpc: SolanaRpc,
    settings: Any,
    instructions: list[Any],
    payer: Pubkey,
) -> UnsignedTransaction:
    blockhash, last_valid = await rpc.get_latest_blockhash()
    encoded = to_unsigned_transaction(instructions, payer, blockhash)

    try:
        simulation = await rpc.simulate_transaction(encoded)
    except RpcError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Simulation call failed: {exc.rpc_message}",
        ) from exc

    if simulation.get("err") is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Transaction would fail on-chain",
                "error": simulation["err"],
                "logs": simulation.get("logs") or [],
            },
        )

    return UnsignedTransaction(
        transaction=encoded,
        blockhash=blockhash,
        last_valid_block_height=last_valid,
        simulation_logs=simulation.get("logs") or [],
    )


@router.post("/initialize", response_model=UnsignedTransaction)
async def initialize(
    user: CurrentUserDep, settings: SettingsDep, rpc: RpcDep
) -> UnsignedTransaction:
    program_id = Pubkey.from_string(settings.program_id)
    payer = _parse_wallet(user.wallet)
    return await _compile(rpc, settings, [build_initialize_ix(program_id, payer)], payer)


@router.post("/increment", response_model=UnsignedTransaction)
async def increment(
    user: CurrentUserDep, settings: SettingsDep, rpc: RpcDep
) -> UnsignedTransaction:
    program_id = Pubkey.from_string(settings.program_id)
    authority = _parse_wallet(user.wallet)
    return await _compile(rpc, settings, [build_increment_ix(program_id, authority)], authority)


@router.get("/counter-address")
async def counter_address(settings: SettingsDep) -> dict[str, str]:
    """The PDA the program derives. Handy for the frontend and for debugging."""
    address, bump = counter_pda(Pubkey.from_string(settings.program_id))
    return {"address": str(address), "bump": str(bump)}
