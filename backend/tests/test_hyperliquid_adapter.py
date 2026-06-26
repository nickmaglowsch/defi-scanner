"""Tests for HyperliquidAdapter and FundingCollector."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.collectors.funding import FundingCollector
from app.collectors.hyperliquid import HyperliquidAdapter, _annualize

# ── Sample Hyperliquid API response (3 perp markets) ────────────────────────

_SAMPLE_META = {
    "universe": [
        {"name": "BTC", "szDecimals": 5, "maxLeverage": 50},
        {"name": "ETH", "szDecimals": 3, "maxLeverage": 50},
        {"name": "SOL", "szDecimals": 1, "maxLeverage": 20},
    ],
}

_SAMPLE_ASSET_CTXS = [
    {
        "funding": "0.0001",
        "openInterest": "1500000000",
        "markPx": "65000",
        "oraclePx": "64980",
        "dayNtlVlm": "5000000000",
        "prevDayPx": "64000",
        "midPx": "65000",
        "premium": "0.0003",
        "impactPxs": ["64900", "65100"],
    },
    {
        "funding": "0.00005",
        "openInterest": "2000000000",
        "markPx": "3500",
        "oraclePx": "3498",
        "dayNtlVlm": "8000000000",
        "prevDayPx": "3450",
        "midPx": "3500",
        "premium": "0.0006",
        "impactPxs": ["3490", "3510"],
    },
    {
        "funding": "0.0002",
        "openInterest": "300000000",
        "markPx": "150",
        "oraclePx": "149.5",
        "dayNtlVlm": "1200000000",
        "prevDayPx": "148",
        "midPx": "150",
        "premium": "0.003",
        "impactPxs": ["149", "151"],
    },
]

_SAMPLE_API_RESPONSE = [_SAMPLE_META, _SAMPLE_ASSET_CTXS]


# ── Unit: annualization calculation ──────────────────────────────────────────


def test_annualize_zero_rate():
    assert _annualize(0.0, 1.0) == 0.0


def test_annualize_standard():
    # 0.01% hourly = 0.0001 * 8760 / 1.0 = 0.876 (87.6% APR)
    assert _annualize(0.0001, 1.0) == pytest.approx(0.876)


def test_annualize_eight_hour_interval():
    """Funding every 8h: rate * 8760 / 8"""
    assert _annualize(0.001, 8.0) == pytest.approx(0.001 * 8760 / 8.0)


def test_annualize_twenty_four_hour_interval():
    assert _annualize(0.01, 24.0) == pytest.approx(0.01 * 8760 / 24.0)


# ── Adapter fixture (mock httpx) ─────────────────────────────────────────────


@pytest.fixture
def mock_client() -> AsyncMock:
    """Return an AsyncMock httpx.AsyncClient whose post() returns sample data."""
    client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = _SAMPLE_API_RESPONSE
    client.post.return_value = mock_resp
    return client


@pytest.fixture
def adapter(mock_client: AsyncMock) -> HyperliquidAdapter:
    """HyperliquidAdapter with a mocked httpx client injected."""
    return HyperliquidAdapter(api_url="https://api.hyperliquid.xyz", client=mock_client)


# ── fetch_funding_rates (mocked) ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_funding_rates_returns_correct_count(adapter: HyperliquidAdapter):
    results = await adapter.fetch_funding_rates()
    assert len(results) == 3


@pytest.mark.asyncio
async def test_fetch_funding_rates_returns_expected_keys(adapter: HyperliquidAdapter):
    results = await adapter.fetch_funding_rates()
    expected_keys = {
        "asset",
        "funding_rate",
        "funding_interval_hours",
        "annualized_funding",
        "open_interest",
        "volume_24h",
        "mark_price",
        "index_price",
        "long_short_ratio",
        "raw_payload",
    }
    for r in results:
        assert set(r.keys()) == expected_keys


@pytest.mark.asyncio
async def test_fetch_funding_rates_asset_names(adapter: HyperliquidAdapter):
    results = await adapter.fetch_funding_rates()
    names = [r["asset"] for r in results]
    assert names == ["BTC", "ETH", "SOL"]


@pytest.mark.asyncio
async def test_fetch_funding_rates_annualized_calculation(adapter: HyperliquidAdapter):
    results = await adapter.fetch_funding_rates()
    # BTC: hourly funding 0.0001 → annualized = 0.0001 * 8760 = 0.876
    btc = results[0]
    assert btc["asset"] == "BTC"
    assert btc["funding_rate"] == pytest.approx(0.0001)
    assert btc["funding_interval_hours"] == pytest.approx(1.0)
    assert btc["annualized_funding"] == pytest.approx(0.876)

    # ETH: hourly funding 0.00005 → annualized = 0.00005 * 8760 = 0.438
    eth = results[1]
    assert eth["annualized_funding"] == pytest.approx(0.438)

    # SOL: hourly funding 0.0002 → annualized = 0.0002 * 8760 = 1.752
    sol = results[2]
    assert sol["annualized_funding"] == pytest.approx(1.752)


@pytest.mark.asyncio
async def test_fetch_funding_rates_numeric_fields(adapter: HyperliquidAdapter):
    results = await adapter.fetch_funding_rates()
    btc = results[0]
    assert btc["open_interest"] == pytest.approx(1_500_000_000)
    assert btc["volume_24h"] == pytest.approx(5_000_000_000)
    assert btc["mark_price"] == pytest.approx(65000)
    assert btc["index_price"] == pytest.approx(64980)
    # ponytail: long_short_ratio is neutral 1.0 (see adapter comment)
    assert btc["long_short_ratio"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_fetch_funding_rates_raw_payload(adapter: HyperliquidAdapter):
    results = await adapter.fetch_funding_rates()
    for i, r in enumerate(results):
        assert r["raw_payload"] is _SAMPLE_ASSET_CTXS[i]


@pytest.mark.asyncio
async def test_fetch_funding_rates_empty_universe(
    adapter: HyperliquidAdapter, mock_client: AsyncMock
):
    """When universe is empty, return empty list."""
    empty_resp = MagicMock()
    empty_resp.raise_for_status = MagicMock()
    empty_resp.json.return_value = [{"universe": []}, []]
    mock_client.post.return_value = empty_resp

    results = await adapter.fetch_funding_rates()
    assert results == []


@pytest.mark.asyncio
async def test_fetch_funding_rates_mismatched_lengths(
    adapter: HyperliquidAdapter, mock_client: AsyncMock
):
    """Handles universe and contexts of different lengths gracefully."""
    mismatch_resp = MagicMock()
    mismatch_resp.raise_for_status = MagicMock()
    mismatch_resp.json.return_value = [
        _SAMPLE_META,
        _SAMPLE_ASSET_CTXS[:1],
    ]  # 3 universe, 1 context
    mock_client.post.return_value = mismatch_resp

    results = await adapter.fetch_funding_rates()
    # Should only process up to min(len(universe), len(contexts))
    assert len(results) == 1
    assert results[0]["asset"] == "BTC"


@pytest.mark.asyncio
async def test_fetch_funding_rates_invalid_json(
    adapter: HyperliquidAdapter, mock_client: AsyncMock
):
    """Non-list response should return empty list."""
    bad_resp = MagicMock()
    bad_resp.raise_for_status = MagicMock()
    bad_resp.json.return_value = {"not": "a list"}
    mock_client.post.return_value = bad_resp

    results = await adapter.fetch_funding_rates()
    assert results == []


@pytest.mark.asyncio
async def test_fetch_funding_rates_null_response(
    adapter: HyperliquidAdapter, mock_client: AsyncMock
):
    """None response treated as invalid → empty list."""
    bad_resp = MagicMock()
    bad_resp.raise_for_status = MagicMock()
    bad_resp.json.return_value = None
    mock_client.post.return_value = bad_resp

    results = await adapter.fetch_funding_rates()
    assert results == []


@pytest.mark.asyncio
async def test_fetch_funding_rates_skips_non_dict_context(
    adapter: HyperliquidAdapter, mock_client: AsyncMock
):
    """Non-dict asset context entries are skipped gracefully."""
    meta_with_three = {
        "universe": [
            {"name": "BTC"},
            {"name": "ETH"},
            {"name": "SOL"},
        ],
    }
    # Second entry is a string, not a dict
    contexts = [_SAMPLE_ASSET_CTXS[0], "not-a-dict", _SAMPLE_ASSET_CTXS[2]]
    bad_resp = MagicMock()
    bad_resp.raise_for_status = MagicMock()
    bad_resp.json.return_value = [meta_with_three, contexts]
    mock_client.post.return_value = bad_resp

    results = await adapter.fetch_funding_rates()
    assert len(results) == 2
    assert results[0]["asset"] == "BTC"
    assert results[1]["asset"] == "SOL"


# ── Retry behavior ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_retry_succeeds_on_third_attempt(adapter: HyperliquidAdapter, mock_client: AsyncMock):
    call_count = 0

    async def _failing_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            resp = MagicMock(status_code=500)
            raise httpx.HTTPStatusError("server error", request=MagicMock(), response=resp)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _SAMPLE_API_RESPONSE
        return mock_resp

    mock_client.post.side_effect = _failing_post
    results = await adapter.fetch_funding_rates()
    assert call_count == 3
    assert len(results) == 3


@pytest.mark.asyncio
async def test_retry_exhaustion_raises(
    adapter: HyperliquidAdapter, mock_client: AsyncMock, caplog
):
    status_500 = MagicMock(status_code=500)

    async def _always_fail(*args, **kwargs):
        raise httpx.HTTPStatusError("server error", request=MagicMock(), response=status_500)

    mock_client.post.side_effect = _always_fail

    with caplog.at_level(logging.WARNING):
        with pytest.raises(httpx.HTTPStatusError):
            await adapter.fetch_funding_rates()

    warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("attempt 1/3" in w for w in warnings)
    assert any("attempt 2/3" in w for w in warnings)
    assert any(
        "exhausted all 3 retries" in str(r.message)
        for r in caplog.records
        if r.levelno == logging.ERROR
    )


@pytest.mark.asyncio
async def test_retry_exhaustion_raises_once_on_success(
    adapter: HyperliquidAdapter, mock_client: AsyncMock
):
    """Single attempt — no retries needed."""
    results = await adapter.fetch_funding_rates()
    assert len(results) == 3
    assert mock_client.post.call_count == 1


# ── FundingCollector ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collector_writes_protocol_and_markets(mock_db_session_factory):
    """FundingCollector should insert Protocol, Market, and FundingSnapshot rows."""
    mock_provider = AsyncMock()
    mock_provider.fetch_funding_rates.return_value = [
        {
            "asset": "BTC",
            "funding_rate": 0.0001,
            "funding_interval_hours": 1.0,
            "annualized_funding": 0.876,
            "open_interest": 1_500_000_000,
            "volume_24h": 5_000_000_000,
            "long_short_ratio": 1.0,
            "mark_price": 65000,
            "index_price": 64980,
            "raw_payload": {"test": True},
        },
        {
            "asset": "ETH",
            "funding_rate": 0.00005,
            "funding_interval_hours": 1.0,
            "annualized_funding": 0.438,
            "open_interest": 2_000_000_000,
            "volume_24h": 8_000_000_000,
            "long_short_ratio": 1.0,
            "mark_price": 3500,
            "index_price": 3498,
            "raw_payload": {},
        },
    ]

    collector = FundingCollector(mock_db_session_factory, mock_provider, "Hyperliquid")
    await collector.collect()

    session = mock_db_session_factory._mock_session
    # Protocol (1) + 2 Markets + 2 Snapshots = 5 add calls
    assert session.add.call_count == 5
    assert session.commit.called


@pytest.mark.asyncio
async def test_collector_second_cycle_no_duplicate_protocol(mock_db_session_factory):
    """Second collection cycle should not re-add protocol or markets."""
    mock_provider = AsyncMock()
    mock_provider.fetch_funding_rates.return_value = [
        {
            "asset": "BTC",
            "funding_rate": 0.00015,
            "funding_interval_hours": 1.0,
            "annualized_funding": 1.314,
            "open_interest": 1_600_000_000,
            "volume_24h": 5_500_000_000,
            "long_short_ratio": 1.0,
            "mark_price": 66000,
            "index_price": 65950,
            "raw_payload": {},
        }
    ]

    collector = FundingCollector(mock_db_session_factory, mock_provider, "Hyperliquid")

    # First cycle: everything is new
    await collector.collect()

    # Second cycle: simulate existing rows
    session = mock_db_session_factory._mock_session
    mock_protocol = MagicMock()
    mock_protocol.id = "proto-1"
    mock_market = MagicMock()
    mock_market.id = "market-1"

    # execute() returns protocol then market (two calls)
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
async def test_collector_skips_empty_rates(mock_db_session_factory):
    """When provider returns no rates, no DB writes should happen."""
    mock_provider = AsyncMock()
    mock_provider.fetch_funding_rates.return_value = []

    collector = FundingCollector(mock_db_session_factory, mock_provider, "Hyperliquid")
    await collector.collect()

    session = mock_db_session_factory._mock_session
    assert session.add.call_count == 0


@pytest.mark.asyncio
async def test_collector_protocol_type_and_chain(mock_db_session_factory):
    """Verify Protocol is created with correct type and chain."""
    from app.models.protocol import Protocol as ProtocolModel

    mock_provider = AsyncMock()
    mock_provider.fetch_funding_rates.return_value = [
        {
            "asset": "BTC",
            "funding_rate": 0.0001,
            "funding_interval_hours": 1.0,
            "annualized_funding": 0.876,
            "open_interest": 1_500_000_000,
            "volume_24h": 5_000_000_000,
            "long_short_ratio": 1.0,
            "mark_price": 65000,
            "index_price": 64980,
            "raw_payload": {},
        }
    ]

    collector = FundingCollector(mock_db_session_factory, mock_provider, "Hyperliquid")
    await collector.collect()

    session = mock_db_session_factory._mock_session

    # session.add receives MagicMock Protocol — extract the first one
    added_objects = [call[0][0] for call in session.add.call_args_list]
    protocols = [obj for obj in added_objects if isinstance(obj, ProtocolModel)]
    assert len(protocols) == 1
    proto = protocols[0]
    assert proto.type == "derivatives"
    assert proto.chain == "hyperliquid"
    assert proto.name == "Hyperliquid"


@pytest.mark.asyncio
async def test_collector_market_type_is_perp(mock_db_session_factory):
    """Verify Market is created with market_type='perp'."""
    from app.models.market import Market as MarketModel

    mock_provider = AsyncMock()
    mock_provider.fetch_funding_rates.return_value = [
        {
            "asset": "BTC",
            "funding_rate": 0.0001,
            "funding_interval_hours": 1.0,
            "annualized_funding": 0.876,
            "open_interest": 1_500_000_000,
            "volume_24h": 5_000_000_000,
            "long_short_ratio": 1.0,
            "mark_price": 65000,
            "index_price": 64980,
            "raw_payload": {},
        }
    ]

    collector = FundingCollector(mock_db_session_factory, mock_provider, "Hyperliquid")
    await collector.collect()

    session = mock_db_session_factory._mock_session
    added_objects = [call[0][0] for call in session.add.call_args_list]
    markets = [obj for obj in added_objects if isinstance(obj, MarketModel)]
    assert len(markets) == 1
    assert markets[0].market_type == "perp"
    assert markets[0].asset == "BTC"
