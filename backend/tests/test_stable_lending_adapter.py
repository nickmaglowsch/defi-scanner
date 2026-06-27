"""Tests for StableLendingAdapter (TDD).

Stable lending derives deposit-only markets from existing lending snapshot data
(assets with no meaningful borrow leg). It does NOT simulate leveraged loops.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.collectors.stable_lending import StableLendingAdapter
from app.protocols.registry import RegistryEntry

_ENTRY = RegistryEntry(
    protocol="Stable Lending",
    slug="stable-lending",
    type="lending",
    chain="ethereum",
    data_source="rpc",
    pool_address="0x0000000000000000000000000000000000000000",
    assets={
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    },
)


@pytest.mark.asyncio
async def test_fetch_reserves_returns_list():
    """StableLendingAdapter.fetch_reserves returns a list (may be empty)."""
    adapter = StableLendingAdapter(_ENTRY)
    result = await adapter.fetch_reserves()
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_fetch_reserves_market_type_is_stable_lending():
    """All returned markets have market_type='stable_lending'."""
    adapter = StableLendingAdapter(_ENTRY)
    result = await adapter.fetch_reserves()
    for market in result:
        assert market["market_type"] == "stable_lending"


@pytest.mark.asyncio
async def test_fetch_reserves_has_deposit_apy_no_borrow():
    """Stable lending markets have deposit_apy but borrow_apy is None."""
    adapter = StableLendingAdapter(_ENTRY)
    result = await adapter.fetch_reserves()
    for market in result:
        # deposit_apy may be None if no data source, but key must exist
        assert "deposit_apy" in market
        # borrow_apy must be None (no borrow leg)
        assert market.get("borrow_apy") is None


@pytest.mark.asyncio
async def test_accepts_injectable_client():
    """Adapter accepts an injectable async client."""
    mock_client = AsyncMock()
    adapter = StableLendingAdapter(_ENTRY, client=mock_client)
    assert adapter._client is mock_client
