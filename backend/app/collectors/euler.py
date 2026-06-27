"""Euler V2 adapter — reads EVK vaults via the Euler V3 API preview."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.protocols.registry import RegistryEntry

logger = logging.getLogger("defi_scanner")

_DEFAULT_API_URL = "https://v3.euler.finance/v3"

# ponytail: hard-coded chain mapping; extend when registry adds new chains.
_CHAIN_IDS = {
    "ethereum": 1,
    "base": 8453,
    "arbitrum": 42161,
    "optimism": 10,
    "polygon": 137,
}


class EulerAdapter:
    """Fetches Euler EVK vault data and returns normalized LendingProvider dicts."""

    def __init__(
        self,
        entry: RegistryEntry,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.entry = entry
        self._client = client
        self._owns_client = client is None
        self._api_url = (entry.pool_address or _DEFAULT_API_URL).rstrip("/")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        self._client = httpx.AsyncClient(timeout=30)
        return self._client

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _retry_get(
        self,
        path: str,
        params: dict[str, object],
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """GET JSON endpoint with exponential backoff."""
        backoff = (1, 2, 4)
        last_exc: Exception | None = None
        client = await self._get_client()
        for attempt in range(max_retries):
            try:
                resp = await client.get(path, params=params)
                resp.raise_for_status()
                return resp.json()  # type: ignore[no-any-return]
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    wait = backoff[attempt]
                    logger.warning(
                        "Euler API attempt %d/%d failed, retrying in %ds: %s",
                        attempt + 1,
                        max_retries,
                        wait,
                        exc,
                    )
                    await asyncio.sleep(wait)
        logger.error("Euler API exhausted all %d retries: %s", max_retries, last_exc)
        raise last_exc  # type: ignore[misc]

    async def fetch_reserves(self) -> list[dict[str, object]]:
        """Fetch Euler EVK vaults for the registry assets and normalize them."""
        chain_id = _CHAIN_IDS.get(self.entry.chain)
        if chain_id is None:
            # ponytail: only EVM chains supported by Euler API; add mapping if needed.
            raise NotImplementedError(
                f"ponytail: Euler chain mapping missing for {self.entry.chain}"
            )

        target_symbols = {sym for sym in self.entry.assets}

        results: list[dict[str, object]] = []
        offset = 0
        limit = 1000
        while True:
            data = await self._retry_get(
                f"{self._api_url}/evk/vaults",
                {"chainId": chain_id, "limit": limit, "offset": offset},
            )
            vaults: list[dict[str, Any]] = data.get("data", [])
            meta = data.get("meta", {})

            for vault in vaults:
                asset_info = vault.get("asset") or {}
                symbol = asset_info.get("symbol")
                if target_symbols and symbol not in target_symbols:
                    continue

                decimals = int(asset_info.get("decimals", 18))
                scale = 10**decimals
                total_supplied = float(vault.get("totalAssets", "0")) / scale
                total_borrowed = float(vault.get("totalBorrows", "0")) / scale

                # ponytail: LTV/liquidation threshold/reserve factor are not
                # returned by the list endpoint; fetch individual vault config
                # endpoints if risk parameters are needed.
                results.append(
                    {
                        "asset": symbol or "UNKNOWN",
                        "deposit_apy": float(vault.get("supplyApy", 0)),
                        "borrow_apy": float(vault.get("borrowApy", 0)),
                        "utilization": float(vault.get("utilization", 0)),
                        "available_liquidity": total_supplied - total_borrowed,
                        "total_supplied": total_supplied,
                        "total_borrowed": total_borrowed,
                        "tvl": total_supplied,
                        "ltv_pct": 0.0,
                        "liquidation_threshold_pct": 0.0,
                        "reserve_factor_pct": 0.0,
                        "reward_apy": 0.0,  # ponytail: rewards not returned by this endpoint
                        "chain": self.entry.chain,
                        "protocol": self.entry.protocol,
                        "market_type": "lending",
                        "raw_payload": vault,
                    }
                )

            total = meta.get("total", 0)
            returned = len(vaults)
            if returned == 0:
                break
            offset += returned
            if offset >= total:
                break

        return results
