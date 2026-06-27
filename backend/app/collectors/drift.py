"""Drift perpetuals adapter placeholder."""

from __future__ import annotations

import httpx


class DriftAdapter:
    """Fetches perpetual market funding rates from Drift.

    Implements the FundingProvider protocol (from app.collectors.base).
    """

    def __init__(
        self,
        api_url: str = "https://mainnet-beta.drift.trade",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._client = client
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch_funding_rates(self) -> list[dict[str, object]]:
        """Fetch funding rates for all Drift perp markets.

        # ponytail: Drift funding data is primarily on-chain (Solana program)
        and the public REST surface is not stable enough for a generic adapter.
        Raise until a reliable endpoint or RPC commitment strategy is confirmed.
        """
        raise NotImplementedError(
            "Drift adapter is pending a reliable public funding-rate endpoint"
        )
