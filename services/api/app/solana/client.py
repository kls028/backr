"""Thin async JSON-RPC client for Solana.

Only the handful of methods this service actually calls. A full SDK is not worth
the dependency weight when the backend never signs anything.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Self

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class RpcError(RuntimeError):
    """The node returned a JSON-RPC error object."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"RPC error {code}: {message}")
        self.code = code
        self.rpc_message = message


class SolanaRpc:
    def __init__(self, url: str, *, timeout: float = 20.0) -> None:
        self._url = url
        self._client = httpx.AsyncClient(timeout=timeout)
        self._request_id = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.3, max=3),
        reraise=True,
    )
    async def _call(self, method: str, params: list[Any] | None = None) -> Any:
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or [],
        }

        response = await self._client.post(self._url, json=payload)
        response.raise_for_status()
        body = response.json()

        if "error" in body:
            error = body["error"]
            raise RpcError(error.get("code", 0), error.get("message", "unknown"))

        return body.get("result")

    async def get_latest_blockhash(self, commitment: str = "confirmed") -> tuple[str, int]:
        """Return (blockhash, last_valid_block_height)."""
        result = await self._call("getLatestBlockhash", [{"commitment": commitment}])
        value = result["value"]
        return value["blockhash"], int(value["lastValidBlockHeight"])

    async def get_version(self) -> dict[str, Any]:
        result: dict[str, Any] = await self._call("getVersion")
        return result

    async def get_slot(self, commitment: str = "confirmed") -> int:
        result = await self._call("getSlot", [{"commitment": commitment}])
        return int(result)

    async def get_account_info(
        self, address: str, commitment: str = "confirmed"
    ) -> dict[str, Any] | None:
        result = await self._call(
            "getAccountInfo",
            [address, {"encoding": "base64", "commitment": commitment}],
        )
        value: dict[str, Any] | None = result.get("value") if result else None
        return value

    async def get_signatures_for_address(
        self,
        address: str,
        *,
        limit: int = 100,
        before: str | None = None,
        until: str | None = None,
        commitment: str = "confirmed",
    ) -> list[dict[str, Any]]:
        options: dict[str, Any] = {"limit": limit, "commitment": commitment}
        if before:
            options["before"] = before
        if until:
            options["until"] = until

        result = await self._call("getSignaturesForAddress", [address, options])
        return list(result or [])

    async def get_transaction(
        self, signature: str, commitment: str = "confirmed"
    ) -> dict[str, Any] | None:
        result = await self._call(
            "getTransaction",
            [
                signature,
                {
                    "encoding": "jsonParsed",
                    "commitment": commitment,
                    "maxSupportedTransactionVersion": 0,
                },
            ],
        )
        return result if isinstance(result, dict) else None

    async def simulate_transaction(self, tx_base64: str) -> dict[str, Any]:
        result = await self._call(
            "simulateTransaction",
            [
                tx_base64,
                {"encoding": "base64", "sigVerify": False, "replaceRecentBlockhash": True},
            ],
        )
        value: dict[str, Any] = result["value"]
        return value
