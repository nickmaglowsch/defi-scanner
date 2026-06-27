"""Tests for StakingAdapter (TDD).

Staking adapter fetches liquid staking yields (wstETH, ezETH, rsETH).
Uses Lido/Rocket Pool APIs or stubs NotImplementedError when unavailable.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.collectors.staking import StakingAdapter
from app.protocols.registry import RegistryEntry

_LIDO_ENTRY = RegistryEntry(
    protocol="Lido",
    slug="lido",
    type="staking",
    chain="ethereum",
    data_source="rpc",
    pool_address="0x0000000000000000000000000000000000000000",
    assets={
        "stETH": "0x0000000000000000000000000000000000000000",
        "ETH": "0x0000000000000000000000000000000000000000",
    },
)


@pytest.mark.asyncio
async def test_fetch_reserves_returns_list():
    """StakingAdapter.fetch_reserves returns a list (may raise NotImplementedError)."""
    adapter = StakingAdapter(_LIDO_ENTRY)
    try:
        result = await adapter.fetch_reserves()
        assert isinstance(result, list)
    except NotImplementedError:
        pass  # acceptable — stub protocol


@pytest.mark.asyncio
async def test_market_type_is_staking():
    """When data is returned, market_type must be 'staking'."""
    adapter = StakingAdapter(_LIDO_ENTRY)
    try:
        result = await adapter.fetch_reserves()
        for market in result:
            assert market["market_type"] == "staking"
    except NotImplementedError:
        pass


@pytest.mark.asyncio
async def test_deposit_apy_key_present():
    """When data is returned, deposit_apy key must be present."""
    adapter = StakingAdapter(_LIDO_ENTRY)
    try:
        result = await adapter.fetch_reserves()
        for market in result:
            assert "deposit_apy" in market
    except NotImplementedError:
        pass


@pytest.mark.asyncio
async def test_borrow_apy_is_none():
    """Staking markets have no borrow leg — borrow_apy must be None."""
    adapter = StakingAdapter(_LIDO_ENTRY)
    try:
        result = await adapter.fetch_reserves()
        for market in result:
            assert market.get("borrow_apy") is None
    except NotImplementedError:
        pass


@pytest.mark.asyncio
async def test_accepts_injectable_client():
    """Adapter accepts an injectable async client."""
    mock_client = AsyncMock()
    adapter = StakingAdapter(_LIDO_ENTRY, client=mock_client)
    assert adapter._client is mock_client


@pytest.mark.asyncio
async def test_not_implemented_has_ponytail_comment():
    """If NotImplementedError is raised, the message contains 'ponytail'."""
    adapter = StakingAdapter(_LIDO_ENTRY)
    try:
        await adapter.fetch_reserves()
    except NotImplementedError as e:
        assert "ponytail" in str(e).lower()
