"""Tests for MorphoAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.collectors.morpho import MorphoAdapter
from app.protocols.registry import RegistryEntry

_ENTRY = RegistryEntry(
    protocol="Morpho",
    slug="morpho",
    type="lending",
    chain="ethereum",
    data_source="graphql",
    pool_address="https://api.morpho.org/graphql",
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
    "data": {
        "markets": {
            "items": [
                {
                    "marketId": "0xabc123",
                    "loanAsset": {
                        "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                        "symbol": "USDC",
                        "decimals": 6,
                    },
                    "collateralAsset": {
                        "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                        "symbol": "WETH",
                        "decimals": 18,
                    },
                    "lltv": "860000000000000000",
                    "state": {
                        "supplyAssets": 1_000_000_000_000,
                        "borrowAssets": 500_000_000_000,
                        "liquidityAssets": 500_000_000_000,
                        "supplyApy": 0.05,
                        "borrowApy": 0.08,
                        "utilization": 0.5,
                        "fee": 0.0015,
                    },
                },
                {
                    "marketId": "0xdef456",
                    "loanAsset": {
                        "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                        "symbol": "USDC",
                        "decimals": 6,
                    },
                    "collateralAsset": {
                        "address": "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0",
                        "symbol": "wstETH",
                        "decimals": 18,
                    },
                    "lltv": "945000000000000000",
                    "state": {
                        "supplyAssets": 2_000_000_000,
                        "borrowAssets": 1_000_000_000,
                        "liquidityAssets": 1_000_000_000,
                        "supplyApy": 0.04,
                        "borrowApy": 0.06,
                        "utilization": 0.5,
                        "fee": 0,
                    },
                },
            ]
        }
    }
}


@pytest.fixture
def mock_client() -> AsyncMock:
    """Mock httpx.AsyncClient returning the sample Morpho GraphQL payload."""
    client = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = _SAMPLE_RESPONSE
    client.post.return_value = resp
    return client


@pytest.fixture
def adapter(mock_client: AsyncMock) -> MorphoAdapter:
    return MorphoAdapter(_ENTRY, client=mock_client)


# ── fetch_reserves ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_reserves_returns_expected_keys(adapter: MorphoAdapter) -> None:
    results = await adapter.fetch_reserves()
    assert len(results) == 2
    for r in results:
        assert set(r.keys()) == _REQUIRED_KEYS


@pytest.mark.asyncio
async def test_fetch_reserves_asset_naming(adapter: MorphoAdapter) -> None:
    results = await adapter.fetch_reserves()
    names = {r["asset"] for r in results}
    assert names == {"USDC/WETH", "USDC/wstETH"}


@pytest.mark.asyncio
async def test_fetch_reserves_numeric_conversions(adapter: MorphoAdapter) -> None:
    results = await adapter.fetch_reserves()
    usdc_weth = next(r for r in results if r["asset"] == "USDC/WETH")

    assert usdc_weth["total_supplied"] == pytest.approx(1_000_000.0)
    assert usdc_weth["total_borrowed"] == pytest.approx(500_000.0)
    assert usdc_weth["available_liquidity"] == pytest.approx(500_000.0)
    assert usdc_weth["tvl"] == pytest.approx(1_000_000.0)
    assert usdc_weth["deposit_apy"] == pytest.approx(5.0)
    assert usdc_weth["borrow_apy"] == pytest.approx(8.0)
    assert usdc_weth["utilization"] == pytest.approx(0.5)
    assert usdc_weth["ltv_pct"] == pytest.approx(86.0)
    assert usdc_weth["liquidation_threshold_pct"] == pytest.approx(86.0)
    assert usdc_weth["reserve_factor_pct"] == pytest.approx(0.15)
    assert usdc_weth["reward_apy"] == 0.0


@pytest.mark.asyncio
async def test_fetch_reserves_metadata_fields(adapter: MorphoAdapter) -> None:
    results = await adapter.fetch_reserves()
    for r in results:
        assert r["chain"] == "ethereum"
        assert r["protocol"] == "Morpho"
        assert r["market_type"] == "lending"
        assert isinstance(r["raw_payload"], dict)


@pytest.mark.asyncio
async def test_fetch_reserves_skips_null_state(
    adapter: MorphoAdapter, mock_client: AsyncMock
) -> None:
    bad_response = {
        "data": {
            "markets": {
                "items": [
                    {
                        "marketId": "0xbad",
                        "loanAsset": {
                            "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                            "symbol": "USDC",
                            "decimals": 6,
                        },
                        "collateralAsset": None,
                        "lltv": "860000000000000000",
                        "state": None,
                    }
                ]
            }
        }
    }
    mock_client.post.return_value.json.return_value = bad_response
    results = await adapter.fetch_reserves()
    assert results == []


@pytest.mark.asyncio
async def test_fetch_reserves_filters_by_loan_asset(
    adapter: MorphoAdapter, mock_client: AsyncMock
) -> None:
    await adapter.fetch_reserves()
    call = mock_client.post.call_args
    assert call is not None
    payload = call.kwargs.get("json") or call.args[1]
    variables = payload["variables"]
    assert variables["where"]["chainId_in"] == [1]
    assert "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48" in variables["where"]["loanAssetAddress_in"]


@pytest.mark.asyncio
async def test_fetch_reserves_empty_assets_returns_empty() -> None:
    empty_entry = RegistryEntry(
        protocol="Morpho",
        slug="morpho",
        type="lending",
        chain="ethereum",
        data_source="graphql",
        pool_address="https://api.morpho.org/graphql",
        assets={},
    )
    adapter = MorphoAdapter(empty_entry, client=AsyncMock(spec=httpx.AsyncClient))
    results = await adapter.fetch_reserves()
    assert results == []


@pytest.mark.asyncio
async def test_unsupported_chain_raises() -> None:
    entry = RegistryEntry(
        protocol="Morpho",
        slug="morpho",
        type="lending",
        chain="solana",
        data_source="graphql",
        pool_address="https://api.morpho.org/graphql",
        assets={"USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"},
    )
    adapter = MorphoAdapter(entry, client=AsyncMock(spec=httpx.AsyncClient))
    with pytest.raises(NotImplementedError, match="ponytail"):
        await adapter.fetch_reserves()
