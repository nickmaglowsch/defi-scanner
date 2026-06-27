"""Tests for SparkAdapter."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.collectors.spark import SparkAdapter
from app.protocols.registry import RegistryEntry

_ENTRY = RegistryEntry(
    protocol="Spark",
    slug="spark",
    type="lending",
    chain="ethereum",
    data_source="rpc",
    pool_address="0xC13e21B648A5Ee794902342038FF3aDAB66BE987",
    rpc_url="http://fake",
    assets={
        "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    },
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


@pytest.fixture
def adapter(mock_web3_init) -> SparkAdapter:
    """Spark adapter with a mocked Web3 stack."""
    a = SparkAdapter(_ENTRY)

    mock_w3 = MagicMock()
    a.w3 = mock_w3
    a.pool = mock_w3.eth.contract.return_value

    a.pool.functions.getReservesList.return_value.call.return_value = list(_ENTRY.assets.values())

    ltv = 8000
    lq_th = 8250
    rf = 1000
    config_data = (ltv << 16) | (lq_th << 32) | (rf << 0)

    mock_rd = MagicMock()
    mock_rd.call.return_value = (
        config_data,
        10**27,  # liquidityIndex
        5 * 10**25,  # liquidityRate
        10**27,  # variableBorrowIndex
        3 * 10**25,  # currentVariableBorrowRate
        0,  # currentStableBorrowRate
        1,  # lastUpdateTimestamp
        0,  # id
        "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # aTokenAddress
        "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",  # stableDebtTokenAddress
        "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",  # variableDebtTokenAddress
        "0xDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",  # interestRateStrategyAddress
        0,  # accruedToTreasury
        0,  # unbacked
        0,  # isolationModeTotalDebt
    )
    a.pool.functions.getReserveData.return_value = mock_rd

    mock_ts = MagicMock()
    mock_ts.call.return_value = 10**24
    mock_w3.eth.contract.return_value.functions.totalSupply.return_value = mock_ts

    return a


# ── fetch_reserves ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_reserves_returns_expected_keys(adapter: SparkAdapter) -> None:
    results = await adapter.fetch_reserves()
    assert len(results) == 2
    for r in results:
        assert set(r.keys()) == _REQUIRED_KEYS
        assert r["protocol"] == "Spark"
        assert r["chain"] == "ethereum"
        assert r["market_type"] == "lending"


@pytest.mark.asyncio
async def test_fetch_reserves_deposit_and_borrow_apy(adapter: SparkAdapter) -> None:
    results = await adapter.fetch_reserves()
    for r in results:
        assert r["deposit_apy"] == pytest.approx(5.0)
        assert r["borrow_apy"] == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_fetch_reserves_config_conversions(adapter: SparkAdapter) -> None:
    results = await adapter.fetch_reserves()
    for r in results:
        assert r["ltv_pct"] == pytest.approx(80.0)
        assert r["liquidation_threshold_pct"] == pytest.approx(82.5)
        assert r["reserve_factor_pct"] == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_fetch_reserves_utilization(adapter: SparkAdapter) -> None:
    _set_erc20_supplies(adapter.w3, supplied=1e24, borrowed=5e23)
    results = await adapter.fetch_reserves()
    for r in results:
        assert r["total_supplied"] == 1e24
        assert r["total_borrowed"] == 5e23
        assert r["utilization"] == pytest.approx(0.5)
        assert r["available_liquidity"] == pytest.approx(5e23)
        assert r["tvl"] == 1e24


@pytest.mark.asyncio
async def test_fetch_reserves_empty_tracked(adapter: SparkAdapter) -> None:
    adapter.pool.functions.getReservesList.return_value.call.return_value = [
        "0xDEAD000000000000000000000000000000000000",
    ]
    results = await adapter.fetch_reserves()
    assert results == []


@pytest.mark.asyncio
async def test_fetch_reserves_skips_failed_asset(adapter: SparkAdapter) -> None:
    addr_seq: list[str] = []

    def _failing_get_reserve_data(addr: str):
        addr_seq.append(addr)
        if len(set(addr_seq)) == 1:
            raise ConnectionError("RPC timeout")
        mock_rd = MagicMock()
        mock_rd.call.return_value = (
            0, 10**27, 5 * 10**25, 10**27, 3 * 10**25, 0, 1, 0,
            "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
            "0xDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",
            0, 0, 0,
        )
        return mock_rd

    adapter.pool.functions.getReserveData.side_effect = _failing_get_reserve_data
    results = await adapter.fetch_reserves()
    assert len(results) == 1
    assert results[0]["asset"] == "WETH"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _set_erc20_supplies(w3_mock: MagicMock, supplied: float, borrowed: float) -> None:
    """Return custom totalSupply values based on token address."""

    def _eth_contract(address=None, abi=None):
        contract = MagicMock()
        is_erc20 = any(item.get("name") == "totalSupply" for item in (abi or []))
        if is_erc20:
            ts = MagicMock()
            addr_lower = (address or "").lower()
            if "aaaaaaaa" in addr_lower:
                ts.call.return_value = int(supplied)
            elif "cccccccc" in addr_lower:
                ts.call.return_value = int(borrowed)
            else:
                ts.call.return_value = 0
            contract.functions.totalSupply.return_value = ts
        else:
            original = w3_mock.eth.contract.return_value
            contract.functions = original.functions
        return contract

    w3_mock.eth.contract.side_effect = _eth_contract
