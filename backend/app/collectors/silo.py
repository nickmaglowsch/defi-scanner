"""Silo Finance adapter.

Silo Finance uses isolated markets (one per collateral asset pair). Each
market has a dedicated contract; the borrow asset can appear multiple times
with different collaterals (e.g. USDC-ETH, USDC-wstETH).

The Silo app (app.silo.finance) is a Next.js SPA with no stable public REST
API as of 2026. The TheGraph subgraph requires an API key.

# ponytail: no reliable public Silo REST API found; subgraph requires auth.
# Implement when either a public subgraph key is provisioned or Silo ships
# an open API (track: https://docs.silo.finance).
"""

from __future__ import annotations

import httpx

from app.protocols.registry import RegistryEntry


class SiloAdapter:
    """Placeholder for Silo Finance isolated-market adapter.

    Raises NotImplementedError until a reliable public data source is available.
    When implemented, each isolated market (borrow asset + collateral) must
    produce one entry with asset named as 'borrowSymbol-collateralSymbol'.
    """

    def __init__(
        self,
        entry: RegistryEntry,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.entry = entry
        self._client = client

    async def fetch_reserves(self) -> list[dict[str, object]]:
        # ponytail: Silo has no public REST API; TheGraph subgraph requires API key.
        # Implement per-market entries as 'borrowSymbol-collateralSymbol' when
        # a public data source is available (e.g. official Silo API or open subgraph).
        raise NotImplementedError(
            "ponytail: Silo Finance has no public REST API; "
            "subgraph (https://thegraph.com) requires an API key — "
            "provision key or use direct RPC reads via SiloLens contract"
        )
