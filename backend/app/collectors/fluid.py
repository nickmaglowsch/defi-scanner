"""Fluid (Instadapp) adapter — reads vault data via the public REST API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.protocols.registry import RegistryEntry

logger = logging.getLogger("defi_scanner")

_DEFAULT_API_URL = "https://api.fluid.instadapp.io"

# ponytail: hard-coded chain mapping; extend when registry adds new chains.
_CHAIN_IDS = {
    "ethereum": 1,
    "base": 8453,
    "arbitrum": 42161,
    "optimism": 10,
    "polygon": 137,
}

# Fluid rates and collateral factors are in basis points (10000 = 100%).
_BPS = 10_000


class FluidAdapter:
    """Fetches Fluid vault data and returns normalized LendingProvider dicts.

    The Fluid API at /v2/{chainId}/vaults returns isolated vault positions
    where each entry has a supply token (collateral) and a borrow token (debt).
    Asset name is formatted as 'supplySymbol/borrowSymbol' to match the
    isolated-market convention used by Morpho.
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
        """Fetch Fluid vaults for the registry chain and normalize them."""
        chain_id = _CHAIN_IDS.get(self.entry.chain)
        if chain_id is None:
            # ponytail: only EVM chains supported by Fluid API; add mapping if needed.
            raise NotImplementedError(
                f"ponytail: Fluid chain mapping missing for {self.entry.chain}"
            )

        client = await self._get_client()
        resp = await client.get(f"{self._api_url}/v2/{chain_id}/vaults")
        resp.raise_for_status()
        vaults: list[dict[str, Any]] = resp.json()

        results: list[dict[str, object]] = []
        for vault in vaults:
            supply_token = vault.get("supplyToken", {}).get("token0", {})
            borrow_token = vault.get("borrowToken", {}).get("token0", {})

            supply_sym = supply_token.get("symbol", "UNKNOWN")
            borrow_sym = borrow_token.get("symbol", "UNKNOWN")
            supply_decimals = int(supply_token.get("decimals", 18))
            borrow_decimals = int(borrow_token.get("decimals", 18))
            supply_price = float(supply_token.get("price", 0) or 0)

            # Rates are in basis points: 157 bps = 1.57%
            supply_rate_bps = int(vault.get("supplyRate", {}).get("vault", {}).get("rate", 0))
            borrow_rate_bps = int(vault.get("borrowRate", {}).get("vault", {}).get("rate", 0))

            # Risk parameters are also in basis points
            cf_bps = int(vault.get("collateralFactor", 0))
            lt_bps = int(vault.get("liquidationThreshold", 0))

            total_supply_raw = int(vault.get("totalSupply", 0))
            total_borrow_raw = int(vault.get("totalBorrow", 0))
            total_supply = total_supply_raw / (10**supply_decimals)
            total_borrow = total_borrow_raw / (10**borrow_decimals)
            tvl_usd = total_supply * supply_price

            # ponytail: available_liquidity expressed in supply token units (collateral);
            # switching to borrow-token liquidity would need borrow price.
            available_liquidity = total_supply - (total_borrow_raw / (10**borrow_decimals))
            if available_liquidity < 0:
                available_liquidity = 0.0

            utilization = total_borrow_raw / total_supply_raw if total_supply_raw else 0.0

            results.append(
                {
                    "asset": f"{supply_sym}/{borrow_sym}",
                    "deposit_apy": supply_rate_bps / 100,
                    "borrow_apy": borrow_rate_bps / 100,
                    "utilization": utilization,
                    "available_liquidity": available_liquidity,
                    "total_supplied": total_supply,
                    "total_borrowed": total_borrow,
                    "tvl": tvl_usd,
                    "ltv_pct": cf_bps / 100,
                    "liquidation_threshold_pct": lt_bps / 100,
                    "reserve_factor_pct": 0.0,
                    "reward_apy": 0.0,
                    "chain": self.entry.chain,
                    "protocol": self.entry.protocol,
                    "market_type": "lending",
                    "raw_payload": vault,
                }
            )

        return results
