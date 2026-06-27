"""Morpho Blue adapter — reads lending markets via the public GraphQL API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.protocols.registry import RegistryEntry

logger = logging.getLogger("defi_scanner")

_DEFAULT_API_URL = "https://api.morpho.org/graphql"
_WAD = 10**18

# ponytail: hard-coded chain mapping; extend when registry adds new chains.
_CHAIN_IDS = {
    "ethereum": 1,
    "base": 8453,
    "arbitrum": 42161,
    "optimism": 10,
    "polygon": 137,
}

_MARKETS_QUERY = """
query Markets($where: MarketFilters, $first: Int, $skip: Int) {
  markets(where: $where, first: $first, skip: $skip) {
    items {
      marketId
      loanAsset { address symbol decimals }
      collateralAsset { address symbol decimals }
      lltv
      state {
        supplyAssets
        borrowAssets
        liquidityAssets
        supplyApy
        borrowApy
        utilization
        fee
      }
    }
  }
}
"""


class MorphoAdapter:
    """Fetches Morpho Blue market data and returns normalized LendingProvider dicts."""

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

    async def _retry_post(
        self, query: str, variables: dict[str, object], max_retries: int = 3
    ) -> dict[str, Any]:
        """POST GraphQL query with exponential backoff."""
        backoff = (1, 2, 4)
        last_exc: Exception | None = None
        client = await self._get_client()
        for attempt in range(max_retries):
            try:
                resp = await client.post(
                    self._api_url, json={"query": query, "variables": variables}
                )
                resp.raise_for_status()
                return resp.json()  # type: ignore[no-any-return]
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    wait = backoff[attempt]
                    logger.warning(
                        "Morpho API attempt %d/%d failed, retrying in %ds: %s",
                        attempt + 1,
                        max_retries,
                        wait,
                        exc,
                    )
                    await asyncio.sleep(wait)
        logger.error("Morpho API exhausted all %d retries: %s", max_retries, last_exc)
        raise last_exc  # type: ignore[misc]

    async def fetch_reserves(self) -> list[dict[str, object]]:
        """Fetch Morpho markets for the registry assets and normalize them."""
        chain_id = _CHAIN_IDS.get(self.entry.chain)
        if chain_id is None:
            # ponytail: only EVM chains supported by Morpho API; add mapping if needed.
            raise NotImplementedError(
                f"ponytail: Morpho chain mapping missing for {self.entry.chain}"
            )

        loan_addresses = [addr for addr in self.entry.assets.values() if addr]
        if not loan_addresses:
            return []

        variables: dict[str, object] = {
            "where": {
                "chainId_in": [chain_id],
                "loanAssetAddress_in": loan_addresses,
            },
            "first": 1000,
            "skip": 0,
        }

        data = await self._retry_post(_MARKETS_QUERY, variables)
        items: list[dict[str, Any]] = (
            data.get("data", {}).get("markets", {}).get("items", [])
        )

        results: list[dict[str, object]] = []
        for item in items:
            state = item.get("state")
            if not state:
                continue

            loan_asset = item.get("loanAsset") or {}
            collateral_asset = item.get("collateralAsset") or {}
            decimals = int(loan_asset.get("decimals", 18))
            scale = 10**decimals

            def _to_float(raw: int) -> float:
                return float(raw) / scale

            total_supplied = _to_float(state["supplyAssets"])
            total_borrowed = _to_float(state["borrowAssets"])
            available_liquidity = _to_float(state["liquidityAssets"])

            lltv = int(item.get("lltv", 0))
            ltv_pct = lltv / _WAD * 100

            # ponytail: Morpho Blue has a single LLTV that acts as both max LTV
            # and liquidation threshold; split the field if the API ever exposes
            # them separately.
            results.append(
                {
                    "asset": f"{loan_asset.get('symbol', 'UNKNOWN')}"
                    f"/{collateral_asset.get('symbol', 'UNKNOWN')}",
                    "deposit_apy": float(state["supplyApy"]) * 100,
                    "borrow_apy": float(state["borrowApy"]) * 100,
                    "utilization": float(state["utilization"]),
                    "available_liquidity": available_liquidity,
                    "total_supplied": total_supplied,
                    "total_borrowed": total_borrowed,
                    "tvl": total_supplied,
                    "ltv_pct": ltv_pct,
                    "liquidation_threshold_pct": ltv_pct,
                    "reserve_factor_pct": float(state.get("fee", 0)) * 100,
                    "reward_apy": 0.0,  # ponytail: rewards not returned by this endpoint
                    "chain": self.entry.chain,
                    "protocol": self.entry.protocol,
                    "market_type": "lending",
                    "raw_payload": item,
                }
            )

        return results
