"""Moonwell adapter — reads lending markets via the public REST API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.protocols.registry import RegistryEntry

logger = logging.getLogger("defi_scanner")

_DEFAULT_API_URL = "https://api.moonwell.fi"

# ponytail: hard-coded chain mapping; extend when registry adds new chains.
_CHAIN_IDS = {
    "base": 8453,
    "moonbeam": 1284,
    "optimism": 10,
}


class MoonwellAdapter:
    """Fetches Moonwell market data and returns normalized LendingProvider dicts.

    Moonwell is a Compound-fork deployed primarily on Base. The API returns
    APYs already in percent and USD amounts already in USD, so no conversion
    is needed beyond collateralFactor (which is a 0–1 ratio → multiply by 100).
    """

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

    async def fetch_reserves(self) -> list[dict[str, object]]:
        """Fetch Moonwell markets for the registry chain and normalize them."""
        chain_id = _CHAIN_IDS.get(self.entry.chain)
        if chain_id is None:
            # ponytail: only Base/Moonbeam supported; add mapping if needed.
            raise NotImplementedError(
                f"ponytail: Moonwell chain mapping missing for {self.entry.chain}"
            )

        client = await self._get_client()
        resp = await client.get(
            f"{self._api_url}/v1/markets", params={"chainId": chain_id}
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        markets: list[dict[str, Any]] = data.get("data", [])

        results: list[dict[str, object]] = []
        for market in markets:
            if market.get("deprecated"):
                continue

            cf = float(market.get("collateralFactor", 0))
            total_supplied = float(market.get("totalSupplyUsd", 0))
            total_borrowed = float(market.get("totalBorrowsUsd", 0))
            liquidity = float(market.get("liquidityUsd", 0))

            results.append(
                {
                    "asset": market.get("asset", "UNKNOWN"),
                    "deposit_apy": float(market.get("baseSupplyApy", 0)),
                    "borrow_apy": float(market.get("baseBorrowApy", 0)),
                    "utilization": float(market.get("utilization", 0)),
                    "available_liquidity": liquidity,
                    "total_supplied": total_supplied,
                    "total_borrowed": total_borrowed,
                    "tvl": total_supplied,
                    "ltv_pct": cf * 100,
                    # ponytail: Moonwell uses a single collateralFactor for both
                    # max LTV and liquidation threshold; split if API exposes them.
                    "liquidation_threshold_pct": cf * 100,
                    "reserve_factor_pct": 0.0,
                    "reward_apy": 0.0,
                    "chain": self.entry.chain,
                    "protocol": self.entry.protocol,
                    "market_type": "lending",
                    "raw_payload": market,
                }
            )

        return results
