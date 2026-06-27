"""Tests for EulerAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.collectors.euler import EulerAdapter
from app.protocols.registry import RegistryEntry

_ENTRY = RegistryEntry(
    protocol="Euler",
    slug="euler",
    type="lending",
    chain="ethereum",
    data_source="rest",
    pool_address="https://v3.euler.finance/v3",
    assets={"USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"},
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

_SAMPLE_RESPONSE = {
    "data": [
        {
            "chainId": 1,
            "address": "0xEulerUsdcVault",
            "vaultType": "evk",
            "name": "EVK Vault eUSDC-1",
            "symbol": "eUSDC-1",
            "decimals": 6,
            "asset": {
                "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "symbol": "USDC",
                "decimals": 6,
                "name": "USD Coin",
            },
            "totalAssets": "2000000000000",
            "totalBorrows": "1000000000000",
            "totalSupplyUsd": 2_000_000,
            "totalBorrowsUsd": 1_000_000,
            "utilization": 0.5,
            "supplyApy": 4.5,
            "borrowApy": 6.5,
            "snapshotTimestamp": "2026-06-26T21:00:00.000Z",
            "createdAt": "2026-01-01T00:00:00.000Z",
        },
        {
            "chainId": 1,
            "address": "0xEulerWethVault",
            "vaultType": "evk",
            "name": "EVK Vault eWETH-1",
            "symbol": "eWETH-1",
            "decimals": 18,
            "asset": {
                "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "symbol": "WETH",
                "decimals": 18,
                "name": "Wrapped Ether",
            },
            "totalAssets": "500000000000000000",
            "totalBorrows": "100000000000000000",
            "totalSupplyUsd": 1_500_000,
            "totalBorrowsUsd": 300_000,
            "utilization": 0.2,
            "supplyApy": 1.5,
            "borrowApy": 2.5,
            "snapshotTimestamp": "2026-06-26T21:00:00.000Z",
            "createdAt": "2026-01-01T00:00:00.000Z",
        },
    ],
    "meta": {"total": 2, "offset": 0, "limit": 1000, "chainId": "1"},
}


@pytest.fixture
def mock_client() -> AsyncMock:
    """Mock httpx.AsyncClient returning the sample Euler vaults payload."""
    client = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = _SAMPLE_RESPONSE
    client.get.return_value = resp
    return client


@pytest.fixture
def adapter(mock_client: AsyncMock) -> EulerAdapter:
    return EulerAdapter(_ENTRY, client=mock_client)


# ── fetch_reserves ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_reserves_returns_expected_keys(adapter: EulerAdapter) -> None:
    results = await adapter.fetch_reserves()
    assert len(results) == 1
    assert set(results[0].keys()) == _REQUIRED_KEYS


@pytest.mark.asyncio
async def test_fetch_reserves_filters_by_asset_symbol(adapter: EulerAdapter) -> None:
    results = await adapter.fetch_reserves()
    assert [r["asset"] for r in results] == ["USDC"]


@pytest.mark.asyncio
async def test_fetch_reserves_numeric_conversions(adapter: EulerAdapter) -> None:
    results = await adapter.fetch_reserves()
    usdc = results[0]

    assert usdc["total_supplied"] == pytest.approx(2_000_000.0)
    assert usdc["total_borrowed"] == pytest.approx(1_000_000.0)
    assert usdc["available_liquidity"] == pytest.approx(1_000_000.0)
    assert usdc["tvl"] == pytest.approx(2_000_000.0)
    assert usdc["deposit_apy"] == pytest.approx(4.5)
    assert usdc["borrow_apy"] == pytest.approx(6.5)
    assert usdc["utilization"] == pytest.approx(0.5)
    assert usdc["ltv_pct"] == 0.0
    assert usdc["liquidation_threshold_pct"] == 0.0
    assert usdc["reserve_factor_pct"] == 0.0
    assert usdc["reward_apy"] == 0.0


@pytest.mark.asyncio
async def test_fetch_reserves_metadata_fields(adapter: EulerAdapter) -> None:
    results = await adapter.fetch_reserves()
    r = results[0]
    assert r["chain"] == "ethereum"
    assert r["protocol"] == "Euler"
    assert r["market_type"] == "lending"
    assert r["raw_payload"]["symbol"] == "eUSDC-1"


@pytest.mark.asyncio
async def test_fetch_reserves_paginates(adapter: EulerAdapter, mock_client: AsyncMock) -> None:
    page1 = {
        "data": [_SAMPLE_RESPONSE["data"][0]],
        "meta": {"total": 2, "offset": 0, "limit": 1, "chainId": "1"},
    }
    page2 = {
        "data": [
            {
                **_SAMPLE_RESPONSE["data"][1],
                "asset": {
                    "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                    "symbol": "USDC",
                    "decimals": 6,
                    "name": "USD Coin",
                },
            }
        ],
        "meta": {"total": 2, "offset": 1, "limit": 1, "chainId": "1"},
    }

    async def _paged_get(*args, **kwargs):
        params = kwargs.get("params") or {}
        offset = params.get("offset", 0)
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = page1 if offset == 0 else page2
        return resp

    mock_client.get.side_effect = _paged_get
    results = await adapter.fetch_reserves()
    assert len(results) == 2
    assert mock_client.get.call_count == 2


@pytest.mark.asyncio
async def test_fetch_respects_base_url() -> None:
    entry = RegistryEntry(
        protocol="Euler",
        slug="euler",
        type="lending",
        chain="ethereum",
        data_source="rest",
        pool_address="https://custom.euler.finance/v3",
        assets={"USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"},
    )
    client = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"data": [], "meta": {"total": 0}}
    client.get.return_value = resp

    adapter = EulerAdapter(entry, client=client)
    await adapter.fetch_reserves()
    assert client.get.call_args.args[0].startswith("https://custom.euler.finance/v3")


@pytest.mark.asyncio
async def test_unsupported_chain_raises() -> None:
    entry = RegistryEntry(
        protocol="Euler",
        slug="euler",
        type="lending",
        chain="solana",
        data_source="rest",
        pool_address="https://v3.euler.finance/v3",
        assets={"USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"},
    )
    adapter = EulerAdapter(entry, client=AsyncMock(spec=httpx.AsyncClient))
    with pytest.raises(NotImplementedError, match="ponytail"):
        await adapter.fetch_reserves()
