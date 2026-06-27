"""Integration tests — LendingCollector and FundingCollector with mocked providers.

Uses the mock_db_session_factory from conftest.py and mocked adapter objects.
Verifies that snapshots are written with correct chain, protocol, and market_type.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.collectors.funding import FundingCollector
from app.collectors.lending import LendingCollector

_FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> object:
    return json.loads((_FIXTURES / name).read_text())


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_session_for_lending(session_factory: MagicMock) -> MagicMock:
    """Configure the mock session so Protocol/Market upserts work end-to-end."""
    session = session_factory._mock_session

    # upsert_protocol: first execute → no existing, flush gives id
    # upsert_market:   second execute → no existing, flush gives id
    # snapshot:        flush, then commit
    # Trigger calc uses a second factory() call — return same ctx.

    # session.execute.scalar_one_or_none already returns None (from conftest).
    # Protocol/Market get a generated UUID id on flush — give them real attributes.
    proto = MagicMock()
    proto.id = "proto-id-aave"
    proto.chain = "ethereum"

    market = MagicMock()
    market.id = "market-id-usdc"
    market.market_type = "lending"
    market.chain = "ethereum"

    # Sequence: protocol execute, market execute, ... repeat for each asset
    # scalar_one_or_none always None → insert path
    session.execute.return_value = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = None

    # flush creates the ORM row — simulate id generation via session.add side effect
    added: list = []

    def _capture_add(obj: object) -> None:
        # Assign ids to Protocol/Market objects so downstream code works
        from app.models import Market, Protocol

        if isinstance(obj, Protocol):
            obj.id = "proto-id-fake"
        elif isinstance(obj, Market):
            obj.id = "market-id-fake"
        added.append(obj)

    session.add.side_effect = _capture_add
    session._added = added
    return session


# ── LendingCollector ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lending_collector_aave_writes_snapshot(mock_db_session_factory) -> None:
    """LendingCollector with Aave-shaped reserve dicts writes a LendingSnapshot.

    Verifies chain='ethereum', market_type='lending' are present on the added row.
    """
    session = _mock_session_for_lending(mock_db_session_factory)

    aave_reserves = [
        {
            "asset": "USDC",
            "chain": "ethereum",
            "protocol": "Aave V3",
            "market_type": "lending",
            "deposit_apy": 5.0,
            "borrow_apy": 3.0,
            "utilization": 0.7,
            "available_liquidity": 2_000_000.0,
            "total_supplied": 5_000_000.0,
            "total_borrowed": 3_500_000.0,
            "tvl": 5_000_000.0,
            "raw_payload": {"configuration": {"ltv_pct": 80.0, "liquidation_threshold_pct": 85.0}},
        }
    ]

    provider = AsyncMock()
    provider.fetch_reserves.return_value = aave_reserves

    with patch("app.collectors.lending.LendingCollector._trigger_calc", new=AsyncMock()):
        collector = LendingCollector(mock_db_session_factory, provider, "Aave V3")
        await collector.collect()

    from app.models import LendingSnapshot, Market, Protocol

    added_markets = [o for o in session._added if isinstance(o, Market)]
    added_snapshots = [o for o in session._added if isinstance(o, LendingSnapshot)]
    added_protocols = [o for o in session._added if isinstance(o, Protocol)]

    assert len(added_protocols) == 1, "expected one Protocol row"
    assert added_protocols[0].chain == "ethereum"

    assert len(added_markets) == 1, "expected one Market row"
    assert added_markets[0].market_type == "lending"
    assert added_markets[0].chain == "ethereum"

    assert len(added_snapshots) == 1, "expected one LendingSnapshot row"
    assert added_snapshots[0].deposit_apy == pytest.approx(5.0)
    assert added_snapshots[0].borrow_apy == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_lending_collector_morpho_writes_snapshot(mock_db_session_factory) -> None:
    """LendingCollector with Morpho-shaped reserve dicts writes a LendingSnapshot."""
    session = _mock_session_for_lending(mock_db_session_factory)

    morpho_reserves = [
        {
            "asset": "USDC/WETH",
            "chain": "ethereum",
            "protocol": "Morpho",
            "market_type": "lending",
            "deposit_apy": 4.8,
            "borrow_apy": 6.5,
            "utilization": 0.60,
            "available_liquidity": 2_000_000.0,
            "total_supplied": 5_000_000.0,
            "total_borrowed": 3_000_000.0,
            "tvl": 5_000_000.0,
            "raw_payload": {},
        }
    ]

    provider = AsyncMock()
    provider.fetch_reserves.return_value = morpho_reserves

    with patch("app.collectors.lending.LendingCollector._trigger_calc", new=AsyncMock()):
        collector = LendingCollector(mock_db_session_factory, provider, "Morpho")
        await collector.collect()

    from app.models import Market, Protocol

    added_markets = [o for o in session._added if isinstance(o, Market)]
    added_protocols = [o for o in session._added if isinstance(o, Protocol)]

    assert added_protocols[0].name == "Morpho"
    assert added_markets[0].market_type == "lending"
    assert added_markets[0].chain == "ethereum"


@pytest.mark.asyncio
async def test_lending_collector_spark_writes_snapshot(mock_db_session_factory) -> None:
    """LendingCollector with Spark-shaped reserve dicts writes a LendingSnapshot with correct chain."""
    session = _mock_session_for_lending(mock_db_session_factory)

    spark_reserves = [
        {
            "asset": "DAI",
            "chain": "ethereum",
            "protocol": "Spark",
            "market_type": "lending",
            "deposit_apy": 3.5,
            "borrow_apy": 4.0,
            "utilization": 0.55,
            "available_liquidity": 1_000_000.0,
            "total_supplied": 2_000_000.0,
            "total_borrowed": 1_100_000.0,
            "tvl": 2_000_000.0,
            "raw_payload": {},
        }
    ]

    provider = AsyncMock()
    provider.fetch_reserves.return_value = spark_reserves

    with patch("app.collectors.lending.LendingCollector._trigger_calc", new=AsyncMock()):
        collector = LendingCollector(mock_db_session_factory, provider, "Spark")
        await collector.collect()

    from app.models import Market

    added_markets = [o for o in session._added if isinstance(o, Market)]
    assert added_markets[0].chain == "ethereum"
    assert added_markets[0].market_type == "lending"


@pytest.mark.asyncio
async def test_lending_collector_empty_returns_early(mock_db_session_factory) -> None:
    """LendingCollector with empty fetch_reserves does not call session.add."""
    session = mock_db_session_factory._mock_session

    provider = AsyncMock()
    provider.fetch_reserves.return_value = []

    collector = LendingCollector(mock_db_session_factory, provider, "Empty")
    await collector.collect()

    session.add.assert_not_called()


# ── FundingCollector ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_funding_collector_hyperliquid_writes_snapshot(mock_db_session_factory) -> None:
    """FundingCollector with Hyperliquid-shaped rates writes a FundingSnapshot with market_type='perp'."""
    session = _mock_session_for_lending(mock_db_session_factory)

    hl_rates = [
        {
            "asset": "BTC",
            "funding_rate": 0.0001,
            "funding_interval_hours": 1.0,
            "annualized_funding": 8.76,
            "open_interest": 1_000_000.0,
            "volume_24h": 50_000_000.0,
            "long_short_ratio": 1.0,
            "mark_price": 65_000.0,
            "index_price": 65_010.0,
            "raw_payload": {},
        }
    ]

    provider = AsyncMock()
    provider.fetch_funding_rates.return_value = hl_rates

    with patch("app.collectors.funding.FundingCollector._trigger_calc", new=AsyncMock()):
        collector = FundingCollector(mock_db_session_factory, provider, "Hyperliquid")
        await collector.collect()

    from app.models import FundingSnapshot, Market, Protocol

    added_protocols = [o for o in session._added if isinstance(o, Protocol)]
    added_markets = [o for o in session._added if isinstance(o, Market)]
    added_snapshots = [o for o in session._added if isinstance(o, FundingSnapshot)]

    assert added_protocols[0].name == "Hyperliquid"
    assert added_protocols[0].type == "derivatives"
    assert added_markets[0].market_type == "perp"
    assert added_snapshots[0].funding_rate == pytest.approx(0.0001)
    assert added_snapshots[0].annualized_funding == pytest.approx(8.76)


@pytest.mark.asyncio
async def test_funding_collector_gmx_writes_snapshot(mock_db_session_factory) -> None:
    """FundingCollector with GMX-shaped rates writes a FundingSnapshot."""
    session = _mock_session_for_lending(mock_db_session_factory)

    gmx_rates = [
        {
            "asset": "ETH",
            "funding_rate": 0.00005,
            "funding_interval_hours": 1.0,
            "annualized_funding": 4.38,
            "open_interest": 500_000.0,
            "volume_24h": 20_000_000.0,
            "long_short_ratio": 1.1,
            "mark_price": 3_500.0,
            "index_price": 3_502.0,
            "raw_payload": {},
        }
    ]

    provider = AsyncMock()
    provider.fetch_funding_rates.return_value = gmx_rates

    with patch("app.collectors.funding.FundingCollector._trigger_calc", new=AsyncMock()):
        collector = FundingCollector(mock_db_session_factory, provider, "GMX")
        await collector.collect()

    from app.models import Market

    added_markets = [o for o in session._added if isinstance(o, Market)]
    assert added_markets[0].market_type == "perp"
    assert added_markets[0].asset == "ETH"


@pytest.mark.asyncio
async def test_funding_collector_empty_returns_early(mock_db_session_factory) -> None:
    """FundingCollector with empty fetch_funding_rates does not call session.add."""
    session = mock_db_session_factory._mock_session

    provider = AsyncMock()
    provider.fetch_funding_rates.return_value = []

    collector = FundingCollector(mock_db_session_factory, provider, "Empty")
    await collector.collect()

    session.add.assert_not_called()
