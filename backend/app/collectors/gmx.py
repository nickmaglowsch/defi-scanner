"""GMX perpetuals adapter placeholder."""

from __future__ import annotations

import httpx


class GmxAdapter:
    """Fetches perpetual market funding rates from GMX.

    Implements the FundingProvider protocol (from app.collectors.base).
    """

    def __init__(
        self,
        api_url: str = "https://arbitrum-api.gmxinfra.io",
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
        """Fetch funding rates for all GMX perp markets.

        # ponytail: GMX v2 funding rates, OI and volume are not available from a
        # single reliable public REST endpoint. The token-price endpoint only
        # returns oracle prices. Raise until a stable source is confirmed.
        """
        raise NotImplementedError(
            "GMX adapter is pending a reliable public funding-rate endpoint"
        )
