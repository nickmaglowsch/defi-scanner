"""Tests for MoonwellAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.collectors.moonwell import MoonwellAdapter
from app.protocols.registry import RegistryEntry

_ENTRY = RegistryEntry(
    protocol="Moonwell",
    slug="moonwell",
    type="lending",
    chain="base",
    data_source="rest",
    pool_address="https://api.moonwell.fi",
    assets={"USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"},
)

_REQUIRED_KEYS = {
    "asset",
    "deposit_apy",
    "borrow_apy",
    "utilization",
    "available_liquidity",
    "total_supplied",
    "total_borrowed",
    "tvl",
    "ltv_pct",
    "liquidation_threshold_pct",
    "reserve_factor_pct",
    "reward_apy",
    "chain",
    "protocol",
    "market_type",
    "raw_payload",
}

# Moonwell markets: APYs are already in percent, USD amounts are already USD
_SAMPLE_RESPONSE = {
    "success": True,
    "data": [
        {
            "asset": "USDC",
            "assetAddress": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "mToken": "mUSDC",
            "mTokenAddress": "0xEdc817A28E8B93B03976FBd4a3dDBc9f7D176c22",
            "deprecated": False,
            "baseSupplyApy": 9.5,
            "baseBorrowApy": 11.8,
            "totalSupplyApr": 9.9,
            "totalBorrowApr": 11.8,
            "totalSupplyUsd": 15_000_000.0,
            "totalBorrowsUsd": 13_500_000.0,
            "liquidityUsd": 1_500_000.0,
            "utilization": 0.9,
            "collateralFactor": 0.88,
        },
        {
            "asset": "ETH",
            "assetAddress": "0x0000000000000000000000000000000000000000",
            "mToken": "mWETH",
            "mTokenAddress": "0x628ff693426583D9a7FB391E54366292F509D457",
            "deprecated": False,
            "baseSupplyApy": 0.89,
            "baseBorrowApy": 1.18,
            "totalSupplyApr": 1.09,
            "totalBorrowApr": 0.94,
            "totalSupplyUsd": 7_000_000.0,
            "totalBorrowsUsd": 6_000_000.0,
            "liquidityUsd": 1_000_000.0,
            "utilization": 0.857,
            "collateralFactor": 0.84,
        },
        {
            "asset": "deprecated",
            "assetAddress": "0xdeadbeef",
            "mToken": "mDEP",
            "mTokenAddress": "0xdeadbeef",
            "deprecated": True,
            "baseSupplyApy": 0.0,
            "baseBorrowApy": 0.0,
            "totalSupplyApr": 0.0,
            "totalBorrowApr": 0.0,
            "totalSupplyUsd": 0.0,
            "totalBorrowsUsd": 0.0,
            "liquidityUsd": 0.0,
            "utilization": 0.0,
            "collateralFactor": 0.0,
        },
    ],
    "meta": {"command": "markets", "chain": "eip155:8453", "timestamp": "2026-06-26T00:00:00Z"},
}


@pytest.fixture
def mock_client() -> AsyncMock:
    """Mock httpx.AsyncClient returning the sample Moonwell markets payload."""
    client = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = _SAMPLE_RESPONSE
    client.get.return_value = resp
    return client


@pytest.fixture
def adapter(mock_client: AsyncMock) -> MoonwellAdapter:
    return MoonwellAdapter(_ENTRY, client=mock_client)


# ── fetch_reserves ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_reserves_returns_expected_keys(adapter: MoonwellAdapter) -> None:
    results = await adapter.fetch_reserves()
    assert len(results) >= 1
    for r in results:
        assert set(r.keys()) == _REQUIRED_KEYS


@pytest.mark.asyncio
async def test_fetch_reserves_skips_deprecated(adapter: MoonwellAdapter) -> None:
    results = await adapter.fetch_reserves()
    assets = [r["asset"] for r in results]
    assert "deprecated" not in assets


@pytest.mark.asyncio
async def test_fetch_reserves_numeric_conversions(adapter: MoonwellAdapter) -> None:
    results = await adapter.fetch_reserves()
    usdc = next(r for r in results if r["asset"] == "USDC")

    assert usdc["deposit_apy"] == pytest.approx(9.5)
    assert usdc["borrow_apy"] == pytest.approx(11.8)
    assert usdc["utilization"] == pytest.approx(0.9)
    assert usdc["total_supplied"] == pytest.approx(15_000_000.0)
    assert usdc["total_borrowed"] == pytest.approx(13_500_000.0)
    assert usdc["available_liquidity"] == pytest.approx(1_500_000.0)
    assert usdc["tvl"] == pytest.approx(15_000_000.0)
    # collateralFactor 0.88 → 88%
    assert usdc["ltv_pct"] == pytest.approx(88.0)
    assert usdc["liquidation_threshold_pct"] == pytest.approx(88.0)
    assert usdc["reserve_factor_pct"] == 0.0
    assert usdc["reward_apy"] == 0.0


@pytest.mark.asyncio
async def test_fetch_reserves_metadata_fields(adapter: MoonwellAdapter) -> None:
    results = await adapter.fetch_reserves()
    for r in results:
        assert r["chain"] == "base"
        assert r["protocol"] == "Moonwell"
        assert r["market_type"] == "lending"
        assert isinstance(r["raw_payload"], dict)


@pytest.mark.asyncio
async def test_fetch_reserves_uses_chain_id_in_request(
    adapter: MoonwellAdapter, mock_client: AsyncMock
) -> None:
    await adapter.fetch_reserves()
    call_kwargs = mock_client.get.call_args.kwargs
    params = call_kwargs.get("params") or {}
    assert params.get("chainId") == 8453  # base chain ID


@pytest.mark.asyncio
async def test_unsupported_chain_raises() -> None:
    entry = RegistryEntry(
        protocol="Moonwell",
        slug="moonwell",
        type="lending",
        chain="solana",
        data_source="rest",
        pool_address="https://api.moonwell.fi",
        assets={"USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"},
    )
    adapter = MoonwellAdapter(entry, client=AsyncMock(spec=httpx.AsyncClient))
    with pytest.raises(NotImplementedError, match="ponytail"):
        await adapter.fetch_reserves()
