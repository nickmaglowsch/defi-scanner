"""Tests for history_agg.get_yield_history, get_percentile, get_historical_rank (TDD)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

from app.calculations.history_agg import get_historical_rank, get_percentile, get_yield_history
from app.models import FundingSnapshot, LendingSnapshot, Market, Protocol


# ── Seed helpers ─────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(UTC)


async def _seed_protocol(session, name: str = None) -> str:
    pid = str(uuid4())
    name = name or f"proto-{pid[:8]}"
    proto = Protocol(id=pid, name=name, type="dex")
    session.add(proto)
    await session.flush()
    return pid


async def _seed_market(session, protocol_id: str, asset: str = "USDC", market_type: str = "lending") -> str:
    mid = str(uuid4())
    market = Market(id=mid, protocol_id=protocol_id, asset=asset, market_type=market_type)
    session.add(market)
    await session.flush()
    return mid


async def _seed_lending_snapshot(session, market_id: str, observed_at: datetime, deposit_apy: float) -> None:
    snap = LendingSnapshot(
        id=str(uuid4()),
        market_id=market_id,
        observed_at=observed_at,
        deposit_apy=deposit_apy,
    )
    session.add(snap)
    await session.flush()


async def _seed_funding_snapshot(session, market_id: str, observed_at: datetime, annualized_funding: float) -> None:
    snap = FundingSnapshot(
        id=str(uuid4()),
        market_id=market_id,
        observed_at=observed_at,
        annualized_funding=annualized_funding,
    )
    session.add(snap)
    await session.flush()


# ── 1. Basic aggregates ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_basic_aggregates(db_session):
    """Market with snapshots across 30d → today/yesterday/avg_7d/avg_30d match hand-computed values."""
    now = _now()
    pid = await _seed_protocol(db_session)
    mid = await _seed_market(db_session, pid)

    # today (most recent): 10.0
    await _seed_lending_snapshot(db_session, mid, now - timedelta(hours=1), 10.0)
    # yesterday (~24h back): 8.0
    await _seed_lending_snapshot(db_session, mid, now - timedelta(hours=25), 8.0)
    # 7d bucket (3d, 5d): 6.0, 4.0
    await _seed_lending_snapshot(db_session, mid, now - timedelta(days=3), 6.0)
    await _seed_lending_snapshot(db_session, mid, now - timedelta(days=5), 4.0)
    # 30d bucket (15d, 20d): 2.0, 3.0
    await _seed_lending_snapshot(db_session, mid, now - timedelta(days=15), 2.0)
    await _seed_lending_snapshot(db_session, mid, now - timedelta(days=20), 3.0)

    result = await get_yield_history(db_session, {mid}, "lending_snapshots", "deposit_apy")

    assert mid in result
    agg = result[mid]

    # today = most recent snapshot value
    assert agg["today"] == pytest.approx(10.0)
    # yesterday = nearest snapshot to latest - 24h (the 25h-ago one)
    assert agg["yesterday"] == pytest.approx(8.0)
    # avg_7d = all snapshots within last 7d relative to latest: 10, 8, 6, 4 → mean=7.0
    assert agg["avg_7d"] == pytest.approx(7.0)
    # avg_30d = all snapshots within last 30d: 10, 8, 6, 4, 2, 3 → mean=5.5
    assert agg["avg_30d"] == pytest.approx(5.5)


# ── 2. Sparse / missing buckets ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sparse_market_only_today(db_session):
    """Market with only 1 recent snapshot → today set, yesterday/avg_7d/avg_30d are None or float."""
    now = _now()
    pid = await _seed_protocol(db_session)
    mid = await _seed_market(db_session, pid)

    await _seed_lending_snapshot(db_session, mid, now - timedelta(hours=1), 5.0)

    result = await get_yield_history(db_session, {mid}, "lending_snapshots", "deposit_apy")

    agg = result[mid]
    assert agg["today"] == pytest.approx(5.0)
    # Only 1 snapshot; no snapshot near 24h ago → yesterday is None
    assert agg["yesterday"] is None
    # avg_7d / avg_30d computed from available data (only 1 point) → 5.0
    assert agg["avg_7d"] == pytest.approx(5.0)
    assert agg["avg_30d"] == pytest.approx(5.0)


# ── 3. Multiple markets batched ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_multiple_markets_batched(db_session):
    """Two markets in one call → correct per-market separation, no bleed."""
    now = _now()
    pid = await _seed_protocol(db_session)
    mid_a = await _seed_market(db_session, pid, asset="USDC")
    mid_b = await _seed_market(db_session, pid, asset="USDT")

    # Market A: deposit_apy = 10.0 (today only)
    await _seed_lending_snapshot(db_session, mid_a, now - timedelta(hours=1), 10.0)
    # Market B: deposit_apy = 20.0 (today only)
    await _seed_lending_snapshot(db_session, mid_b, now - timedelta(hours=1), 20.0)

    result = await get_yield_history(db_session, {mid_a, mid_b}, "lending_snapshots", "deposit_apy")

    assert result[mid_a]["today"] == pytest.approx(10.0)
    assert result[mid_b]["today"] == pytest.approx(20.0)
    # Values don't bleed across markets
    assert result[mid_a]["today"] != result[mid_b]["today"]


# ── 4. Empty input ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_input_returns_empty_dict(db_session):
    """Empty market_id set → empty dict, no SQL error."""
    result = await get_yield_history(db_session, set(), "lending_snapshots", "deposit_apy")
    assert result == {}


# ── 5. Funding snapshots (annualized_funding field) ───────────────────────────


@pytest.mark.asyncio
async def test_funding_snapshots_annualized_funding(db_session):
    """Works with funding_snapshots / annualized_funding (generic field param)."""
    now = _now()
    pid = await _seed_protocol(db_session)
    mid = await _seed_market(db_session, pid, asset="BTC", market_type="perp")

    await _seed_funding_snapshot(db_session, mid, now - timedelta(hours=1), 15.0)
    await _seed_funding_snapshot(db_session, mid, now - timedelta(hours=25), 12.0)

    result = await get_yield_history(db_session, {mid}, "funding_snapshots", "annualized_funding")

    agg = result[mid]
    assert agg["today"] == pytest.approx(15.0)
    assert agg["yesterday"] == pytest.approx(12.0)


# ── 6. get_percentile — sufficient history ────────────────────────────────────


@pytest.mark.asyncio
async def test_get_percentile_high(db_session):
    """Current value is the max over 90d → percentile near 1.0 (100th)."""
    now = _now()
    pid = await _seed_protocol(db_session)
    mid = await _seed_market(db_session, pid)

    # Seed 25 snapshots over 60 days with values 1..25 (today = 25, the max).
    for i in range(1, 26):
        await _seed_lending_snapshot(
            db_session, mid, now - timedelta(days=60 - i * 2, hours=1), float(i)
        )

    result = await get_percentile(db_session, {mid}, "lending_snapshots", "deposit_apy")
    assert mid in result
    # Current value (25) is the max → percentile ≈ 1.0
    assert result[mid] == pytest.approx(1.0, abs=0.05)


@pytest.mark.asyncio
async def test_get_percentile_low(db_session):
    """Current value is the min over 90d → percentile near 0.0."""
    now = _now()
    pid = await _seed_protocol(db_session)
    mid = await _seed_market(db_session, pid)

    # Seed 25 snapshots, today has value 1 (the min).
    for i in range(1, 26):
        days_ago = i * 2
        await _seed_lending_snapshot(
            db_session, mid, now - timedelta(days=days_ago, hours=1), float(i)
        )
    # Add a "current" snapshot with the lowest value.
    await _seed_lending_snapshot(db_session, mid, now - timedelta(hours=1), 0.5)

    result = await get_percentile(db_session, {mid}, "lending_snapshots", "deposit_apy")
    # 0.5 is below all historical values → percentile near 0.0
    assert result[mid] < 0.1


@pytest.mark.asyncio
async def test_get_percentile_null_when_insufficient_history(db_session):
    """Fewer than 20 points or < 7 days of history → None."""
    now = _now()
    pid = await _seed_protocol(db_session)
    mid = await _seed_market(db_session, pid)

    # Only 3 snapshots — insufficient
    for i in range(3):
        await _seed_lending_snapshot(db_session, mid, now - timedelta(hours=i + 1), float(i + 1))

    result = await get_percentile(db_session, {mid}, "lending_snapshots", "deposit_apy")
    assert result.get(mid) is None


@pytest.mark.asyncio
async def test_get_percentile_empty_input(db_session):
    """Empty market_id set → empty dict."""
    result = await get_percentile(db_session, set(), "lending_snapshots", "deposit_apy")
    assert result == {}


# ── 7. get_historical_rank ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_historical_rank_top(db_session):
    """High percentile → rank string mentions '90d'."""
    now = _now()
    pid = await _seed_protocol(db_session)
    mid = await _seed_market(db_session, pid)

    for i in range(1, 26):
        await _seed_lending_snapshot(
            db_session, mid, now - timedelta(days=60 - i * 2, hours=1), float(i)
        )

    result = await get_historical_rank(db_session, {mid}, "lending_snapshots", "deposit_apy")
    assert mid in result
    assert result[mid] is not None
    assert "90d" in result[mid]


@pytest.mark.asyncio
async def test_get_historical_rank_null_when_insufficient(db_session):
    """< 20 points → None."""
    now = _now()
    pid = await _seed_protocol(db_session)
    mid = await _seed_market(db_session, pid)

    await _seed_lending_snapshot(db_session, mid, now - timedelta(hours=1), 5.0)

    result = await get_historical_rank(db_session, {mid}, "lending_snapshots", "deposit_apy")
    assert result.get(mid) is None
