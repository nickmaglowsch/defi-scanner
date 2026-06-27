"""Stable lending adapter — deposit-only markets, no borrow leg.

Derives stable-lending opportunities synthetically from existing lending market
snapshots for assets where the borrow leg is absent or irrelevant (e.g.
stablecoin-only deposit products). Implements LendingProvider protocol.

market_type = "stable_lending" so the orchestrator skips loop simulation.
"""

from __future__ import annotations

import httpx

from app.protocols.registry import RegistryEntry


class StableLendingAdapter:
    """Deposit-only lending adapter — no borrow-leg, no loop simulation.

    Currently returns an empty list; connect to a real data source when
    available (e.g. Aave E-mode, Euler single-asset vaults, etc.).

    # ponytail: no dedicated stable-lending REST API identified; synthetic
    # derivation from existing lending snapshots is handled at the route level.
    # Implement fetch when a dedicated source is wired in.
    """

    def __init__(
        self,
        entry: RegistryEntry,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.entry = entry
        self._client = client

    async def fetch_reserves(self) -> list[dict[str, object]]:
        """Return deposit-only stable lending markets.

        Returns an empty list until a dedicated data source is available.
        All returned markets have market_type='stable_lending' and borrow_apy=None.
        """
        # ponytail: synthetic derivation from existing lending snapshots handled
        # at route level (filter lending markets with no borrow leg). A dedicated
        # source (Aave E-mode caps, Euler single-asset) is the upgrade path.
        return []

    def _normalize(self, raw: dict) -> dict[str, object]:
        """Normalize a raw market dict into the stable_lending format."""
        return {
            "chain": self.entry.chain,
            "protocol": self.entry.protocol,
            "market_type": "stable_lending",
            "asset": raw.get("asset", ""),
            "deposit_apy": raw.get("deposit_apy"),
            "borrow_apy": None,  # no borrow leg
            "utilization": None,
            "available_liquidity": raw.get("available_liquidity"),
            "total_supplied": raw.get("total_supplied"),
            "total_borrowed": None,
            "tvl": raw.get("tvl"),
            "raw_payload": raw.get("raw_payload"),
        }
