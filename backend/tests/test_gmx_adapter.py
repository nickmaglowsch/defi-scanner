"""Tests for GmxAdapter.

GMX v2 does not expose a reliable public REST endpoint that returns funding
rates, open interest, and volume in one call. The adapter therefore raises
NotImplementedError until a stable data source is confirmed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from app.collectors.gmx import GmxAdapter


@pytest.fixture
def mock_client() -> AsyncMock:
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def adapter(mock_client: AsyncMock) -> GmxAdapter:
    return GmxAdapter(api_url="https://arbitrum-api.gmxinfra.io", client=mock_client)


@pytest.mark.asyncio
async def test_fetch_funding_rates_not_implemented(adapter: GmxAdapter):
    with pytest.raises(NotImplementedError):
        await adapter.fetch_funding_rates()


@pytest.mark.asyncio
async def test_fetch_funding_rates_accepts_injectable_client(mock_client: AsyncMock):
    """The adapter accepts an injected httpx client even when the source
    is not yet implemented."""
    adapter = GmxAdapter(client=mock_client)
    assert adapter._client is mock_client
