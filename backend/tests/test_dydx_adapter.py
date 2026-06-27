"""Tests for DydxAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.collectors.dydx import DydxAdapter, _annualize

# ── Sample dYdX v4 indexer response ──────────────────────────────────────────

_SAMPLE_DYDX_MARKETS = {
    "markets": {
        "BTC-USD": {
            "ticker": "BTC-USD",
            "status": "ACTIVE",
            "oraclePrice": "65000.0",
            "priceChange24H": "100.0",
            "volume24H": "500000000.0",
            "nextFundingRate": "0.0001",
            "openInterest": "1500.0",
            "atomicResolution": -10,
        },
        "ETH-USD": {
            "ticker": "ETH-USD",
            "status": "ACTIVE",
            "oraclePrice": "3500.0",
            "priceChange24H": "5.0",
            "volume24H": "800000000.0",
            "nextFundingRate": "0.00005",
            "openInterest": "20000.0",
            "atomicResolution": -9,
        },
        "SOL-USD": {
            "ticker": "SOL-USD",
            "status": "ACTIVE",
            "oraclePrice": "150.0",
            "priceChange24H": "-2.0",
            "volume24H": "120000000.0",
            "nextFundingRate": "0.0002",
            "openInterest": "300000.0",
            "atomicResolution": -8,
        },
    }
}


# ── Unit: annualization calculation ──────────────────────────────────────────


def test_annualize_zero_rate():
    assert _annualize(0.0, 1.0) == 0.0


def test_annualize_standard():
    # 0.01% hourly = 0.0001 * 8760 / 1.0 = 0.876 (87.6% APR)
    assert _annualize(0.0001, 1.0) == pytest.approx(0.876)


# ── Adapter fixture ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_client() -> AsyncMock:
    """Return an AsyncMock httpx.AsyncClient whose get() returns sample data."""
    client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = _SAMPLE_DYDX_MARKETS
    client.get.return_value = mock_resp
    return client


@pytest.fixture
def adapter(mock_client: AsyncMock) -> DydxAdapter:
    """DydxAdapter with a mocked httpx client injected."""
    return DydxAdapter(api_url="https://indexer.dydx.trade", client=mock_client)


# ── fetch_funding_rates (mocked) ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_funding_rates_returns_correct_count(adapter: DydxAdapter):
    results = await adapter.fetch_funding_rates()
    assert len(results) == 3


@pytest.mark.asyncio
async def test_fetch_funding_rates_returns_expected_keys(adapter: DydxAdapter):
    results = await adapter.fetch_funding_rates()
    expected_keys = {
        "asset",
        "funding_rate",
        "funding_interval_hours",
        "annualized_funding",
        "open_interest",
        "volume_24h",
        "long_short_ratio",
        "mark_price",
        "index_price",
        "raw_payload",
        "chain",
        "protocol",
        "market_type",
    }
    for r in results:
        assert set(r.keys()) == expected_keys


@pytest.mark.asyncio
async def test_fetch_funding_rates_asset_names(adapter: DydxAdapter):
    results = await adapter.fetch_funding_rates()
    names = [r["asset"] for r in results]
    assert names == ["BTC", "ETH", "SOL"]


@pytest.mark.asyncio
async def test_fetch_funding_rates_annualized_calculation(adapter: DydxAdapter):
    results = await adapter.fetch_funding_rates()
    # BTC: hourly funding 0.0001 -> annualized = 0.0001 * 8760 = 0.876
    btc = results[0]
    assert btc["asset"] == "BTC"
    assert btc["funding_rate"] == pytest.approx(0.0001)
    assert btc["funding_interval_hours"] == pytest.approx(1.0)
    assert btc["annualized_funding"] == pytest.approx(0.876)

    # ETH: hourly funding 0.00005 -> annualized = 0.00005 * 8760 = 0.438
    eth = results[1]
    assert eth["annualized_funding"] == pytest.approx(0.438)

    # SOL: hourly funding 0.0002 -> annualized = 0.0002 * 8760 = 1.752
    sol = results[2]
    assert sol["annualized_funding"] == pytest.approx(1.752)


@pytest.mark.asyncio
async def test_fetch_funding_rates_numeric_fields(adapter: DydxAdapter):
    results = await adapter.fetch_funding_rates()
    btc = results[0]
    assert btc["open_interest"] == pytest.approx(1500.0)
    assert btc["volume_24h"] == pytest.approx(500000000.0)
    assert btc["mark_price"] == pytest.approx(65000.0)
    assert btc["index_price"] == pytest.approx(65000.0)
    # ponytail: dYdX markets endpoint does not expose long/short OI breakdown
    assert btc["long_short_ratio"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_fetch_funding_rates_protocol_and_chain(adapter: DydxAdapter):
    results = await adapter.fetch_funding_rates()
    btc = results[0]
    assert btc["protocol"] == "dYdX"
    assert btc["chain"] == "dydx"
    assert btc["market_type"] == "perp"


@pytest.mark.asyncio
async def test_fetch_funding_rates_raw_payload(adapter: DydxAdapter):
    results = await adapter.fetch_funding_rates()
    assert results[0]["raw_payload"] is _SAMPLE_DYDX_MARKETS["markets"]["BTC-USD"]


@pytest.mark.asyncio
async def test_fetch_funding_rates_empty_markets(adapter: DydxAdapter, mock_client: AsyncMock):
    """When markets dict is empty, return empty list."""
    empty_resp = MagicMock()
    empty_resp.raise_for_status = MagicMock()
    empty_resp.json.return_value = {"markets": {}}
    mock_client.get.return_value = empty_resp

    results = await adapter.fetch_funding_rates()
    assert results == []


@pytest.mark.asyncio
async def test_fetch_funding_rates_invalid_response(adapter: DydxAdapter, mock_client: AsyncMock):
    """Non-dict response should return empty list."""
    bad_resp = MagicMock()
    bad_resp.raise_for_status = MagicMock()
    bad_resp.json.return_value = {"not_markets": []}
    mock_client.get.return_value = bad_resp

    results = await adapter.fetch_funding_rates()
    assert results == []


@pytest.mark.asyncio
async def test_fetch_funding_rates_skips_inactive_markets(
    adapter: DydxAdapter, mock_client: AsyncMock
):
    """Inactive markets are skipped."""
    resp_with_inactive = {
        "markets": {
            "BTC-USD": _SAMPLE_DYDX_MARKETS["markets"]["BTC-USD"],
            "CLOSED-USD": {
                "ticker": "CLOSED-USD",
                "status": "CLOSED",
                "oraclePrice": "1.0",
                "volume24H": "0",
                "nextFundingRate": "0",
                "openInterest": "0",
            },
        }
    }
    bad_resp = MagicMock()
    bad_resp.raise_for_status = MagicMock()
    bad_resp.json.return_value = resp_with_inactive
    mock_client.get.return_value = bad_resp

    results = await adapter.fetch_funding_rates()
    assert len(results) == 1
    assert results[0]["asset"] == "BTC"
