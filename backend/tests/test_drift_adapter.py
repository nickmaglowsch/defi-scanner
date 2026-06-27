"""Tests for DriftAdapter.

Drift's public REST surface for live perp funding rates is not stable enough
for a generic adapter. The adapter raises NotImplementedError until a reliable
endpoint is confirmed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from app.collectors.drift import DriftAdapter


@pytest.fixture
def mock_client() -> AsyncMock:
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def adapter(mock_client: AsyncMock) -> DriftAdapter:
    return DriftAdapter(api_url="https://mainnet-beta.drift.trade", client=mock_client)


@pytest.mark.asyncio
async def test_fetch_funding_rates_not_implemented(adapter: DriftAdapter):
    with pytest.raises(NotImplementedError):
        await adapter.fetch_funding_rates()


@pytest.mark.asyncio
async def test_fetch_funding_rates_accepts_injectable_client(mock_client: AsyncMock):
    adapter = DriftAdapter(client=mock_client)
    assert adapter._client is mock_client
