"""Vertex perpetuals adapter placeholder."""

from __future__ import annotations

import httpx


class VertexAdapter:
    """Fetches perpetual market funding rates from Vertex.

    Implements the FundingProvider protocol (from app.collectors.base).
    """

    def __init__(
        self,
        api_url: str = "https://api.prod.vertexprotocol.com",
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
        """Fetch funding rates for all Vertex perp markets.

        # ponytail: Vertex's public REST endpoints for live perp funding rates
        are not stable/documented enough for a generic adapter. Raise until a
        reliable endpoint is confirmed.
        """
        raise NotImplementedError(
            "Vertex adapter is pending a reliable public funding-rate endpoint"
        )
