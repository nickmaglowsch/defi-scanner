"""Tests for VertexAdapter.

Vertex's public REST surface for live perp funding rates is not stable enough
for a generic adapter. The adapter raises NotImplementedError until a reliable
endpoint is confirmed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from app.collectors.vertex import VertexAdapter


@pytest.fixture
def mock_client() -> AsyncMock:
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def adapter(mock_client: AsyncMock) -> VertexAdapter:
    return VertexAdapter(api_url="https://api.prod.vertexprotocol.com", client=mock_client)


@pytest.mark.asyncio
async def test_fetch_funding_rates_not_implemented(adapter: VertexAdapter):
    with pytest.raises(NotImplementedError):
        await adapter.fetch_funding_rates()


@pytest.mark.asyncio
async def test_fetch_funding_rates_accepts_injectable_client(mock_client: AsyncMock):
    adapter = VertexAdapter(client=mock_client)
    assert adapter._client is mock_client
