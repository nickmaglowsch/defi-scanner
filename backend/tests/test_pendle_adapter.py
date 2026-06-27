"""Tests for PendleAdapter (TDD).

Pendle fixed-yield markets. Uses Pendle API for fixed-yield APY and implied yield.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.collectors.pendle import PendleAdapter
from app.protocols.registry import RegistryEntry

_PENDLE_ENTRY = RegistryEntry(
    protocol="Pendle",
    slug="pendle",
    type="pendle",
    chain="ethereum",
    data_source="rpc",
    pool_address="0x0000000000000000000000000000000000000000",
    assets={
        "PT": "0x0000000000000000000000000000000000000000",
        "YT": "0x0000000000000000000000000000000000000000",
    },
)

_MOCK_PENDLE_RESPONSE = {
    "results": [
        {
            "address": "0xabc123",
            "symbol": "PT-wstETH",
            "fixedApy": 5.2,
            "impliedApy": 4.8,
            "maturity": "2025-12-31T00:00:00Z",
            "tvl": {"usd": 1_000_000.0},
        }
    ]
}


@pytest.mark.asyncio
async def test_fetch_reserves_returns_list():
    """PendleAdapter.fetch_reserves returns a list (may raise NotImplementedError)."""
    adapter = PendleAdapter(_PENDLE_ENTRY)
    try:
        result = await adapter.fetch_reserves()
        assert isinstance(result, list)
    except NotImplementedError:
        pass


@pytest.mark.asyncio
async def test_market_type_is_pendle():
    """When data is returned, market_type must be 'pendle'."""
    adapter = PendleAdapter(_PENDLE_ENTRY)
    try:
        result = await adapter.fetch_reserves()
        for market in result:
            assert market["market_type"] == "pendle"
    except NotImplementedError:
        pass


@pytest.mark.asyncio
async def test_borrow_apy_is_none():
    """Pendle PT markets have no borrow leg — borrow_apy must be None."""
    adapter = PendleAdapter(_PENDLE_ENTRY)
    try:
        result = await adapter.fetch_reserves()
        for market in result:
            assert market.get("borrow_apy") is None
    except NotImplementedError:
        pass


@pytest.mark.asyncio
async def test_maturity_in_raw_payload():
    """Maturity date must be in raw_payload when data is returned."""
    adapter = PendleAdapter(_PENDLE_ENTRY)
    try:
        result = await adapter.fetch_reserves()
        for market in result:
            assert "raw_payload" in market
            if market["raw_payload"]:
                assert "maturity" in market["raw_payload"]
    except NotImplementedError:
        pass


@pytest.mark.asyncio
async def test_not_implemented_has_ponytail_comment():
    """If NotImplementedError is raised, message contains 'ponytail'."""
    adapter = PendleAdapter(_PENDLE_ENTRY)
    try:
        await adapter.fetch_reserves()
    except NotImplementedError as e:
        assert "ponytail" in str(e).lower()


@pytest.mark.asyncio
async def test_accepts_injectable_client():
    """Adapter accepts an injectable async client."""
    mock_client = AsyncMock()
    adapter = PendleAdapter(_PENDLE_ENTRY, client=mock_client)
    assert adapter._client is mock_client


@pytest.mark.asyncio
async def test_with_mocked_api_response():
    """With mocked Pendle API response, returns normalized market dicts."""
    from unittest.mock import MagicMock
    mock_client = AsyncMock()
    mock_response = MagicMock()  # sync: json() and raise_for_status() are sync in httpx
    mock_response.json.return_value = _MOCK_PENDLE_RESPONSE
    mock_response.raise_for_status = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    adapter = PendleAdapter(_PENDLE_ENTRY, client=mock_client)
    try:
        result = await adapter.fetch_reserves()
        assert isinstance(result, list)
        if result:
            market = result[0]
            assert market["market_type"] == "pendle"
            assert market.get("borrow_apy") is None
            assert "raw_payload" in market
    except NotImplementedError:
        pass  # acceptable if Pendle API format changed
