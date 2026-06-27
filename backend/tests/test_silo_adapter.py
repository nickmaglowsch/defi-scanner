"""Tests for SiloAdapter.

Silo Finance does not expose a reliable public REST API as of 2026. The adapter
raises NotImplementedError with a ponytail comment to document the blocker.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from app.collectors.silo import SiloAdapter
from app.protocols.registry import RegistryEntry

_ENTRY = RegistryEntry(
    protocol="Silo",
    slug="silo",
    type="lending",
    chain="ethereum",
    data_source="rpc",
    pool_address="0x0000000000000000000000000000000000000000",
    assets={
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    },
)


@pytest.mark.asyncio
async def test_fetch_reserves_raises_not_implemented() -> None:
    """SiloAdapter raises NotImplementedError until a reliable data source is found."""
    adapter = SiloAdapter(_ENTRY, client=AsyncMock(spec=httpx.AsyncClient))
    with pytest.raises(NotImplementedError, match="ponytail"):
        await adapter.fetch_reserves()


@pytest.mark.asyncio
async def test_fetch_reserves_raises_with_descriptive_message() -> None:
    """The NotImplementedError message should explain why."""
    adapter = SiloAdapter(_ENTRY, client=AsyncMock(spec=httpx.AsyncClient))
    with pytest.raises(NotImplementedError) as exc_info:
        await adapter.fetch_reserves()
    message = str(exc_info.value)
    assert "Silo" in message or "silo" in message.lower()
