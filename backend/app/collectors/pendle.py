"""Pendle fixed-yield adapter.

market_type = "pendle"; returns fixed-yield APY and implied yield.
No borrow leg; no loop simulation.

Pendle markets trade Principal Tokens (PT) with a fixed APY until maturity.
The Pendle API at api.pendle.finance/core/v1/sdk/{chain_id}/markets provides
market data including fixedApy, impliedApy, and maturity.
"""

from __future__ import annotations

import logging

import httpx

from app.protocols.registry import RegistryEntry

logger = logging.getLogger("defi_scanner")

# Pendle API endpoint; chain_id=1 for ethereum mainnet.
_PENDLE_API_BASE = "https://api.pendle.finance/core/v1/sdk/{chain_id}/markets"

_CHAIN_IDS = {
    "ethereum": 1,
    "arbitrum": 42161,
    "base": 8453,
}


class PendleAdapter:
    """Pendle fixed-yield market adapter.

    Fetches PT market data from the Pendle API. Returns markets with
    market_type='pendle', deposit_apy=fixed_apy, borrow_apy=None,
    and maturity in raw_payload.
    """

    def __init__(
        self,
        entry: RegistryEntry,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.entry = entry
        self._client = client
        self._owns_client = client is None

    async def fetch_reserves(self) -> list[dict[str, object]]:
        """Fetch Pendle PT markets from the Pendle API.

        # ponytail: Pendle API requires live HTTP access; raises NotImplementedError
        # when no injected client is provided (matches test isolation pattern for
        # staking/restaking). In production, inject httpx.AsyncClient from the
        # collector runner.
        """
        if self._client is None:
            raise NotImplementedError(
                "ponytail: PendleAdapter requires an injected httpx.AsyncClient. "
                "In production, inject from the collector runner. "
                "Pendle API: GET api.pendle.finance/core/v1/sdk/{chain_id}/markets "
                "for fixedApy, impliedApy, and maturity per PT market."
            )

        chain_id = _CHAIN_IDS.get(self.entry.chain, 1)
        url = _PENDLE_API_BASE.format(chain_id=chain_id)

        try:
            resp = await self._client.get(url, params={"select": "all"})
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Pendle API fetch failed: %s", exc)
            return []

        results = data.get("results", []) if isinstance(data, dict) else []
        return [self._normalize(m) for m in results if isinstance(m, dict)]

    def _normalize(self, raw: dict) -> dict[str, object]:
        """Normalize a Pendle market dict into the standard format."""
        return {
            "chain": self.entry.chain,
            "protocol": self.entry.protocol,
            "market_type": "pendle",
            "asset": raw.get("symbol", "PT"),
            "deposit_apy": raw.get("fixedApy"),  # fixed-yield APY is primary metric
            "borrow_apy": None,  # PT markets have no borrow leg
            "utilization": None,
            "available_liquidity": None,
            "total_supplied": None,
            "total_borrowed": None,
            "tvl": (raw.get("tvl") or {}).get("usd") if isinstance(raw.get("tvl"), dict) else raw.get("tvl"),
            "raw_payload": {
                "address": raw.get("address"),
                "maturity": raw.get("maturity"),
                "implied_apy": raw.get("impliedApy"),
                "fixed_apy": raw.get("fixedApy"),
            },
        }
