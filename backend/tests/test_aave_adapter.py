"""Tests for AaveV3Adapter and LendingCollector."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from app.collectors.aave import AaveV3Adapter, _parse_config_data, _ray_to_apy_pct
from app.collectors.lending import LendingCollector
from app.models import Market, Protocol
from app.protocols.registry import RegistryEntry

DEFAULT_POOL = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
TEST_ASSETS = {
    "USDC": "0x1111111111111111111111111111111111111111",
    "USDT": "0x2222222222222222222222222222222222222222",
}

DEFAULT_REGISTRY_ENTRY = RegistryEntry(
    protocol="Aave V3",
    slug="aave-v3",
    type="lending",
    chain="ethereum",
    data_source="rpc",
    pool_address=DEFAULT_POOL,
    assets=TEST_ASSETS,
    rpc_url="http://fake",
)


# ── Unit: RAY conversion ───────────────────────────────────────────────────


def test_ray_to_apy_pct_zero():
    assert _ray_to_apy_pct(0) == 0.0


def test_ray_to_apy_pct_five_percent():
    assert _ray_to_apy_pct(5 * 10**25) == pytest.approx(5.0)


def test_ray_to_apy_pct_twelve_percent():
    assert _ray_to_apy_pct(int(0.125 * 10**27)) == pytest.approx(12.5)


# ── Unit: configuration bit parsing ────────────────────────────────────────


def test_parse_config_data():
    ltv = 7500
    lq_th = 8250
    rf = 2000
    data = (ltv << 16) | (lq_th << 32) | (rf << 0)
    result = _parse_config_data(data)
    assert result["ltv_pct"] == pytest.approx(75.0)
    assert result["liquidation_threshold_pct"] == pytest.approx(82.5)
    assert result["reserve_factor_pct"] == pytest.approx(20.0)


def test_parse_config_data_zeros():
    assert _parse_config_data(0) == {
        "reserve_factor_pct": 0.0,
        "ltv_pct": 0.0,
        "liquidation_threshold_pct": 0.0,
    }


# ── Adapter fixture (mock Web3 constructor → inject mocks) ─────────────────


@pytest.fixture
def adapter():
    """Adapter with an injected mock Web3 client and default return values."""
    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 1

    a = AaveV3Adapter(
        registry_entry=DEFAULT_REGISTRY_ENTRY,
        rpc_url="http://fake",
        client=mock_w3,
    )

    # Default pool functions
    a.pool.functions.getReservesList.return_value.call.return_value = [
        "0x1111111111111111111111111111111111111111",
        "0x2222222222222222222222222222222222222222",
    ]
    mock_rd = MagicMock()
    mock_rd.call.return_value = (
        0,  # configuration bitmask (plain uint256)
        10**27, 5 * 10**25,
        10**27,  # variableBorrowIndex
        3 * 10**25,  # currentVariableBorrowRate
        0,  # currentStableBorrowRate
        1,  # lastUpdateTimestamp
        0,  # id (uint16)
        "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # aTokenAddress
        "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",  # stableDebtTokenAddress
        "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",  # variableDebtTokenAddress
        "0xDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",  # interestRateStrategyAddress
        0,  # accruedToTreasury
        0,  # unbacked
        0,  # isolationModeTotalDebt
    )
    a.pool.functions.getReserveData.return_value = mock_rd

    # Default ERC20 totalSupply: 1e24 for any token
    mock_ts = MagicMock()
    mock_ts.call.return_value = 10**24
    mock_w3.eth.contract.return_value.functions.totalSupply.return_value = mock_ts

    return a


# ── fetch_reserves (mocked) ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_reserves_returns_correct_keys(adapter):
    results = await adapter.fetch_reserves()
    assert len(results) == 2

    for r in results:
        assert r["asset"] in ("USDC", "USDT")
        for key in (
            "chain", "protocol", "market_type", "reward_apy",
            "deposit_apy", "borrow_apy", "utilization",
            "available_liquidity", "total_supplied", "total_borrowed",
            "tvl", "raw_payload",
        ):
            assert key in r
        assert r["chain"] == "ethereum"
        assert r["protocol"] == "Aave V3"
        assert r["market_type"] == "lending"
        assert r["reward_apy"] is None


@pytest.mark.asyncio
async def test_fetch_reserves_raw_payload_includes_config(adapter):
    results = await adapter.fetch_reserves()
    for r in results:
        cfg = r["raw_payload"]["configuration"]
        assert "ltv_pct" in cfg
        assert "liquidation_threshold_pct" in cfg
        assert "reserve_factor_pct" in cfg


@pytest.mark.asyncio
async def test_fetch_reserves_deposit_apy_default(adapter):
    results = await adapter.fetch_reserves()
    for r in results:
        assert r["deposit_apy"] == pytest.approx(5.0)
        assert r["borrow_apy"] == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_fetch_reserves_utilization(adapter):
    """Override ERC20 supplies to verify utilization and related fields."""
    _set_erc20_supplies(adapter.w3, supplied=1e24, borrowed=5e23)
    results = await adapter.fetch_reserves()
    for r in results:
        assert r["total_supplied"] == 1e24
        assert r["total_borrowed"] == 5e23
        assert r["utilization"] == pytest.approx(0.5)
        assert r["available_liquidity"] == pytest.approx(5e23)
        assert r["tvl"] == 1e24


@pytest.mark.asyncio
async def test_fetch_reserves_empty_tracked(adapter):
    """When no tracked assets are in pool reserve list, return empty list."""
    adapter.pool.functions.getReservesList.return_value.call.return_value = [
        "0xDEAD000000000000000000000000000000000000",
    ]
    results = await adapter.fetch_reserves()
    assert results == []


@pytest.mark.asyncio
async def test_fetch_reserves_skips_failed_asset(adapter):
    """If getReserveData exhausts retries for one asset, skip it and continue.

    Function must fail on ALL retry attempts (call_count ≤ 3 per retry loop,
    but since the retry wrapper calls it 3 times before giving up, we raise
    regardless of call_count so the first asset always fails exhaustively).
    """
    # Side effect dict: per-address failure flag
    addr_seq: list[str] = []

    def _failing_get_reserve_data(addr):
        addr_seq.append(addr)
        # First unique address always raises (exhausts all 3 retries)
        if len(set(addr_seq)) == 1:
            raise ConnectionError("RPC timeout")
        mock_rd = MagicMock()
        mock_rd.call.return_value = (
            0,  # configuration bitmask (plain uint256)
            10**27, 5 * 10**25,
            10**27,  # variableBorrowIndex
            3 * 10**25,  # currentVariableBorrowRate
            0,  # currentStableBorrowRate
            1,  # lastUpdateTimestamp
            0,  # id (uint16)
            "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # aTokenAddress
            "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",  # stableDebtTokenAddress
            "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",  # variableDebtTokenAddress
            "0xDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",  # interestRateStrategyAddress
            0,  # accruedToTreasury
            0,  # unbacked
            0,  # isolationModeTotalDebt
        )
        return mock_rd

    adapter.pool.functions.getReserveData.side_effect = _failing_get_reserve_data

    results = await adapter.fetch_reserves()
    assert len(results) == 1
    assert results[0]["asset"] == "USDT"


# ── Retry behavior ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_retry_succeeds_on_third_attempt(adapter, mocker):
    spy = mocker.spy(adapter, "_retry_call")
    call_count = 0

    def _failing_call():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError(f"attempt {call_count}")
        return []

    await adapter._retry_call(_failing_call, max_retries=3)
    assert call_count == 3
    assert spy.call_count == 1


@pytest.mark.asyncio
async def test_retry_exhaustion_raises_and_logs(adapter, caplog):
    call_count = 0

    def _always_fail():
        nonlocal call_count
        call_count += 1
        raise ConnectionError(f"fail {call_count}")

    with caplog.at_level(logging.WARNING):
        with pytest.raises(ConnectionError, match="fail 3"):
            await adapter._retry_call(_always_fail, max_retries=3)

    assert call_count == 3
    warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("attempt 1/3" in w for w in warnings)
    assert any("attempt 2/3" in w for w in warnings)


# ── Utilization calculation ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_utilization_zero_when_total_supplied_zero(adapter):
    _set_erc20_supplies(adapter.w3, supplied=0, borrowed=500)
    results = await adapter.fetch_reserves()
    for r in results:
        assert r["utilization"] == 0.0


@pytest.mark.asyncio
async def test_utilization_full(adapter):
    _set_erc20_supplies(adapter.w3, supplied=1e18, borrowed=1e18)
    results = await adapter.fetch_reserves()
    for r in results:
        assert r["utilization"] == pytest.approx(1.0)


# ── LendingCollector ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collector_writes_protocol_and_markets(mock_db_session_factory, mock_provider):
    mock_provider.fetch_reserves.return_value = [
        {
            "asset": "USDC",
            "deposit_apy": 4.5,
            "borrow_apy": 6.0,
            "utilization": 0.75,
            "available_liquidity": 250.0,
            "total_supplied": 1000.0,
            "total_borrowed": 750.0,
            "tvl": 1000.0,
            "raw_payload": {"test": True},
        }
    ]

    collector = LendingCollector(mock_db_session_factory, mock_provider, "Aave V3")
    await collector.collect()

    session = mock_db_session_factory._mock_session
    assert session.add.call_count >= 3  # Protocol + Market + Snapshot
    assert session.commit.called


@pytest.mark.asyncio
async def test_collector_second_cycle_no_duplicate_protocol(
    mock_db_session_factory, mock_provider
):
    mock_provider.fetch_reserves.return_value = [
        {
            "asset": "USDC",
            "deposit_apy": 5.0,
            "borrow_apy": 7.0,
            "utilization": 0.8,
            "available_liquidity": 200.0,
            "total_supplied": 1000.0,
            "total_borrowed": 800.0,
            "tvl": 1000.0,
            "raw_payload": {},
        }
    ]

    collector = LendingCollector(mock_db_session_factory, mock_provider, "Aave V3")

    # First cycle: everything is new
    await collector.collect()

    # Second cycle: simulate existing rows
    session = mock_db_session_factory._mock_session
    mock_protocol = MagicMock()
    mock_protocol.id = "proto-1"
    mock_market = MagicMock()
    mock_market.id = "market-1"

    # execute() returns protocol then market
    session.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_protocol)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_market)),
    ]

    session.add.reset_mock()
    session.commit.reset_mock()

    await collector.collect()

    # Only snapshot should be added in the second cycle
    assert session.add.call_count == 1
    assert session.commit.called


@pytest.mark.asyncio
async def test_collector_skips_empty_reserves(mock_db_session_factory, mock_provider):
    mock_provider.fetch_reserves.return_value = []

    collector = LendingCollector(mock_db_session_factory, mock_provider, "Aave V3")
    await collector.collect()

    session = mock_db_session_factory._mock_session
    assert session.add.call_count == 0


@pytest.mark.asyncio
async def test_collector_passes_chain_to_protocol_and_market(
    mock_db_session_factory, mock_provider
):
    mock_provider.fetch_reserves.return_value = [
        {
            "asset": "USDC",
            "chain": "base",
            "deposit_apy": 4.5,
            "borrow_apy": 6.0,
            "utilization": 0.75,
            "available_liquidity": 250.0,
            "total_supplied": 1000.0,
            "total_borrowed": 750.0,
            "tvl": 1000.0,
            "raw_payload": {},
        }
    ]

    collector = LendingCollector(mock_db_session_factory, mock_provider, "Aave V3")
    await collector.collect()

    session = mock_db_session_factory._mock_session
    added = [call.args[0] for call in session.add.call_args_list]
    protocol = next(item for item in added if isinstance(item, Protocol))
    market = next(item for item in added if isinstance(item, Market))
    assert protocol.chain == "base"
    assert market.chain == "base"


# ── Helpers ────────────────────────────────────────────────────────────────


def _set_erc20_supplies(w3_mock: MagicMock, supplied: float, borrowed: float) -> None:
    """Configure mock w3.eth.contract to return custom totalSupply values.

    Uses address inspection to distinguish aToken (0xAA..AA)
    from variableDebtToken (0xCC..CC).
    """

    def _eth_contract(address=None, abi=None):
        is_erc20 = any(
            item.get("name") == "totalSupply" for item in (abi or [])
        )
        contract = MagicMock()
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
            # Pool contract — return existing pool mock behavior
            original = w3_mock.eth.contract.return_value
            contract.functions = original.functions
        return contract

    w3_mock.eth.contract.side_effect = _eth_contract
