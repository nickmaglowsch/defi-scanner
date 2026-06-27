"""Tests for RestakingAdapter (TDD).

EigenLayer AVS restaking yields. Stubs NotImplementedError when unavailable.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.collectors.restaking import RestakingAdapter
from app.protocols.registry import RegistryEntry

_EIGEN_ENTRY = RegistryEntry(
    protocol="EigenLayer",
    slug="eigenlayer",
    type="restaking",
    chain="ethereum",
    data_source="rpc",
    pool_address="0x0000000000000000000000000000000000000000",
    assets={
        "ETH": "0x0000000000000000000000000000000000000000",
        "stETH": "0x0000000000000000000000000000000000000000",
    },
)


@pytest.mark.asyncio
async def test_fetch_reserves_raises_not_implemented():
    """RestakingAdapter raises NotImplementedError — EigenLayer AVS data unavailable."""
    adapter = RestakingAdapter(_EIGEN_ENTRY)
    with pytest.raises(NotImplementedError):
        await adapter.fetch_reserves()


@pytest.mark.asyncio
async def test_not_implemented_has_ponytail_comment():
    """NotImplementedError message must contain 'ponytail' to explain the stub."""
    adapter = RestakingAdapter(_EIGEN_ENTRY)
    with pytest.raises(NotImplementedError) as exc_info:
        await adapter.fetch_reserves()
    assert "ponytail" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_not_implemented_mentions_eigenlayer():
    """Error message explains which protocol is missing."""
    adapter = RestakingAdapter(_EIGEN_ENTRY)
    with pytest.raises(NotImplementedError) as exc_info:
        await adapter.fetch_reserves()
    msg = str(exc_info.value).lower()
    assert "eigenlayer" in msg or "restaking" in msg or "avs" in msg


@pytest.mark.asyncio
async def test_accepts_injectable_client():
    """Adapter accepts an injectable async client."""
    mock_client = AsyncMock()
    adapter = RestakingAdapter(_EIGEN_ENTRY, client=mock_client)
    assert adapter._client is mock_client
