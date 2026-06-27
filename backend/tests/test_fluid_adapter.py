"""Tests for FluidAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.collectors.fluid import FluidAdapter
from app.protocols.registry import RegistryEntry

_ENTRY = RegistryEntry(
    protocol="Fluid",
    slug="fluid",
    type="lending",
    chain="ethereum",
    data_source="rest",
    pool_address="https://api.fluid.instadapp.io",
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

# Fluid vault: ETH supplied, USDC borrowed
# supplyRate.vault.rate and borrowRate.vault.rate are in basis points (e.g. 157 = 1.57%)
# collateralFactor and liquidationThreshold are in bps (8500 = 85%, 9000 = 90%)
# totalSupply and totalBorrow are raw token amounts (divided by 10**decimals)
_SAMPLE_RESPONSE = [
    {
        "id": "1",
        "type": "1",
        "address": "0xVault1",
        "supplyToken": {
            "token0": {
                "address": "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
                "symbol": "ETH",
                "decimals": 18,
                "price": "1575.0",
            },
            "token1": {"address": "0x0000000000000000000000000000000000000000"},
        },
        "borrowToken": {
            "token0": {
                "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "symbol": "USDC",
                "decimals": 6,
                "price": "1.0",
            },
            "token1": {"address": "0x0000000000000000000000000000000000000000"},
        },
        "supplyRate": {"liquidity": {"token0": "157"}, "vault": {"rate": "157", "feeRate": "0"}},
        "borrowRate": {"liquidity": {"token0": "823"}, "vault": {"rate": "823", "feeRate": "0"}},
        "collateralFactor": 8500,
        "liquidationThreshold": 9000,
        "totalSupply": "1000000000000000000",  # 1 ETH
        "totalBorrow": "1000000000",  # 1000 USDC (6 decimals)
        "totalSupplyLiquidity": "1000000000000000000",
        "totalBorrowLiquidity": "1000000000",
        "rewards": [],
        "metadata": {"pegged": False},
    },
    {
        "id": "2",
        "type": "1",
        "address": "0xVault2",
        "supplyToken": {
            "token0": {
                "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "symbol": "WETH",
                "decimals": 18,
                "price": "1575.0",
            },
            "token1": {"address": "0x0000000000000000000000000000000000000000"},
        },
        "borrowToken": {
            "token0": {
                "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "symbol": "USDT",
                "decimals": 6,
                "price": "1.0",
            },
            "token1": {"address": "0x0000000000000000000000000000000000000000"},
        },
        "supplyRate": {"liquidity": {"token0": "200"}, "vault": {"rate": "200", "feeRate": "0"}},
        "borrowRate": {"liquidity": {"token0": "900"}, "vault": {"rate": "900", "feeRate": "0"}},
        "collateralFactor": 8000,
        "liquidationThreshold": 8600,
        "totalSupply": "2000000000000000000",  # 2 WETH
        "totalBorrow": "2000000000",  # 2000 USDT
        "totalSupplyLiquidity": "2000000000000000000",
        "totalBorrowLiquidity": "2000000000",
        "rewards": [],
        "metadata": {"pegged": False},
    },
]


@pytest.fixture
def mock_client() -> AsyncMock:
    """Mock httpx.AsyncClient returning the sample Fluid vaults payload."""
    client = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = _SAMPLE_RESPONSE
    client.get.return_value = resp
    return client


@pytest.fixture
def adapter(mock_client: AsyncMock) -> FluidAdapter:
    return FluidAdapter(_ENTRY, client=mock_client)


# ── fetch_reserves ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_reserves_returns_expected_keys(adapter: FluidAdapter) -> None:
    results = await adapter.fetch_reserves()
    assert len(results) >= 1
    for r in results:
        assert set(r.keys()) == _REQUIRED_KEYS


@pytest.mark.asyncio
async def test_fetch_reserves_numeric_conversions(adapter: FluidAdapter) -> None:
    results = await adapter.fetch_reserves()
    eth_usdc = next(r for r in results if r["asset"] == "ETH/USDC")

    # supplyRate 157 bps = 1.57%
    assert eth_usdc["deposit_apy"] == pytest.approx(1.57)
    # borrowRate 823 bps = 8.23%
    assert eth_usdc["borrow_apy"] == pytest.approx(8.23)
    # collateralFactor 8500 bps = 85%
    assert eth_usdc["ltv_pct"] == pytest.approx(85.0)
    # liquidationThreshold 9000 bps = 90%
    assert eth_usdc["liquidation_threshold_pct"] == pytest.approx(90.0)


@pytest.mark.asyncio
async def test_fetch_reserves_asset_naming(adapter: FluidAdapter) -> None:
    results = await adapter.fetch_reserves()
    names = {r["asset"] for r in results}
    assert "ETH/USDC" in names
    assert "WETH/USDT" in names


@pytest.mark.asyncio
async def test_fetch_reserves_tvl_calculation(adapter: FluidAdapter) -> None:
    results = await adapter.fetch_reserves()
    eth_usdc = next(r for r in results if r["asset"] == "ETH/USDC")
    # totalSupply 1e18 raw / 1e18 decimals = 1.0 ETH. TVL uses supply token price: 1.0 * 1575.0 = 1575.0 USD
    assert eth_usdc["tvl"] == pytest.approx(1575.0)
    assert eth_usdc["total_supplied"] == pytest.approx(1.0)
    # totalBorrow is in borrow token (USDC, 6 decimals): 1e9 / 1e6 = 1000.0
    assert eth_usdc["total_borrowed"] == pytest.approx(1000.0)


@pytest.mark.asyncio
async def test_fetch_reserves_metadata_fields(adapter: FluidAdapter) -> None:
    results = await adapter.fetch_reserves()
    for r in results:
        assert r["chain"] == "ethereum"
        assert r["protocol"] == "Fluid"
        assert r["market_type"] == "lending"
        assert isinstance(r["raw_payload"], dict)


@pytest.mark.asyncio
async def test_fetch_reserves_reward_apy_zero(adapter: FluidAdapter) -> None:
    results = await adapter.fetch_reserves()
    for r in results:
        assert r["reward_apy"] == 0.0


@pytest.mark.asyncio
async def test_fetch_reserves_uses_chain_id_in_url(
    adapter: FluidAdapter, mock_client: AsyncMock
) -> None:
    await adapter.fetch_reserves()
    call_url = mock_client.get.call_args.args[0]
    assert "/1/" in call_url  # ethereum chain ID is 1


@pytest.mark.asyncio
async def test_unsupported_chain_raises() -> None:
    entry = RegistryEntry(
        protocol="Fluid",
        slug="fluid",
        type="lending",
        chain="solana",
        data_source="rest",
        pool_address="https://api.fluid.instadapp.io",
        assets={"USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"},
    )
    adapter = FluidAdapter(entry, client=AsyncMock(spec=httpx.AsyncClient))
    with pytest.raises(NotImplementedError, match="ponytail"):
        await adapter.fetch_reserves()
