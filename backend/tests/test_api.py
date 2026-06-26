"""API endpoint tests — FastAPI TestClient with mocked DB session."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app

# ── Fixtures ──────────────────────────────────────────────────────────────────

MOCK_MARKET_ID = str(uuid4())
MOCK_PROTOCOL_ID = str(uuid4())
MOCK_SNAPSHOT_ID = str(uuid4())


@pytest.fixture
def mock_db():
    """Create an AsyncMock session with scalar returns for all query patterns."""
    session = AsyncMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()

    # Default: execute returns empty scalars
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    mock_result.one_or_none.return_value = None
    session.execute.return_value = mock_result

    return session


@pytest.fixture
def client(mock_db):
    """FastAPI TestClient with DB dependency overridden."""

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _proto_row():
    """A simple object simulating a Protocol ORM row with real attributes."""
    return SimpleNamespace(
        id=MOCK_PROTOCOL_ID,
        name="Aave V3",
        type="lending",
        chain="ethereum",
        risk_score=0.5,
    )


def _market_row(asset="USDC", market_type="lending"):
    return SimpleNamespace(
        id=MOCK_MARKET_ID,
        protocol_id=MOCK_PROTOCOL_ID,
        asset=asset,
        market_type=market_type,
    )


def _lending_snapshot_row():
    return SimpleNamespace(
        id=MOCK_SNAPSHOT_ID,
        market_id=MOCK_MARKET_ID,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        deposit_apy=5.0,
        borrow_apy=3.0,
        utilization=0.7,
        available_liquidity=1_000_000.0,
        total_supplied=5_000_000.0,
        total_borrowed=3_500_000.0,
        tvl=10_000_000.0,
    )


def _funding_snapshot_row():
    return SimpleNamespace(
        id=str(uuid4()),
        market_id=MOCK_MARKET_ID,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        funding_rate=0.0001,
        funding_interval_hours=1.0,
        annualized_funding=8.76,
        open_interest=1_000_000.0,
        volume_24h=50_000_000.0,
        long_short_ratio=1.5,
        mark_price=100.0,
        index_price=100.1,
    )


# ── 1. GET /protocols ─────────────────────────────────────────────────────────


def test_get_protocols_returns_list(client, mock_db):
    """GET /api/v1/protocols → 200 with populated list."""
    proto = _proto_row()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [proto]
    mock_db.execute.return_value = mock_result

    resp = client.get("/api/v1/protocols")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "Aave V3"


def test_get_protocols_empty(client, mock_db):
    """GET /api/v1/protocols with no protocols → 200, empty list."""
    resp = client.get("/api/v1/protocols")
    assert resp.status_code == 200
    assert resp.json() == []


# ── 2. GET /assets ────────────────────────────────────────────────────────────


def test_get_assets_returns_list(client, mock_db):
    """GET /api/v1/assets → 200 with distinct asset symbols."""
    # Mock execute returning tuples of (asset,)
    mock_result = MagicMock()
    mock_result.__iter__.return_value = iter([("USDC",), ("WETH",)])
    mock_db.execute.return_value = mock_result

    resp = client.get("/api/v1/assets")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert "USDC" in data
    assert "WETH" in data


def test_get_assets_empty(client, mock_db):
    """GET /api/v1/assets with no markets → 200, empty list."""
    mock_result = MagicMock()
    mock_result.__iter__.return_value = iter([])
    mock_db.execute.return_value = mock_result

    resp = client.get("/api/v1/assets")
    assert resp.status_code == 200
    assert resp.json() == []


# ── 3. GET /funding ───────────────────────────────────────────────────────────


def test_get_funding_returns_list(client, mock_db):
    """GET /api/v1/funding → 200 with asset/protocol labels populated."""
    snap = _funding_snapshot_row()
    market = SimpleNamespace(
        id=MOCK_MARKET_ID, protocol_id=MOCK_PROTOCOL_ID, asset="ETH", market_type="perp"
    )
    protocol = SimpleNamespace(
        id=MOCK_PROTOCOL_ID, name="Hyperliquid", type="funding", chain=None, risk_score=0.3
    )

    snap_result = MagicMock()
    snap_result.scalars.return_value.all.return_value = [snap]

    mp_result = MagicMock()
    mp_result.all.return_value = [(market, protocol)]

    mock_db.execute = AsyncMock(side_effect=[snap_result, mp_result])

    resp = client.get("/api/v1/funding?limit=3")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["asset"] == "ETH"
    assert data[0]["protocol"] == "Hyperliquid"
    assert data[0]["funding_interval_hours"] is not None


def test_get_funding_protocol_filter_excludes_non_matching(client, mock_db):
    """GET /api/v1/funding?protocol=Hyperliquid → excludes non-matching protocols."""
    snap = _funding_snapshot_row()
    market = SimpleNamespace(
        id=MOCK_MARKET_ID, protocol_id=MOCK_PROTOCOL_ID, asset="ETH", market_type="perp"
    )
    protocol = SimpleNamespace(
        id=MOCK_PROTOCOL_ID, name="GMX", type="funding", chain=None, risk_score=0.3
    )

    snap_result = MagicMock()
    snap_result.scalars.return_value.all.return_value = [snap]
    mp_result = MagicMock()
    mp_result.all.return_value = [(market, protocol)]
    mock_db.execute = AsyncMock(side_effect=[snap_result, mp_result])

    resp = client.get("/api/v1/funding?protocol=Hyperliquid")
    assert resp.status_code == 200
    assert resp.json() == []


# ── 4. GET /history ───────────────────────────────────────────────────────────


def test_get_history_requires_market_id(client):
    """GET /api/v1/history without market_id → 400."""
    resp = client.get("/api/v1/history?type=funding")
    assert resp.status_code == 400
    assert "market_id" in resp.json()["detail"].lower()


def test_get_history_invalid_uuid(client):
    """GET /api/v1/history with invalid UUID → 400."""
    resp = client.get("/api/v1/history?type=funding&market_id=not-a-uuid")
    assert resp.status_code == 400


def test_get_history_unknown_type(client):
    """GET /api/v1/history with unknown type → 400."""
    valid_uuid = str(uuid4())
    resp = client.get(f"/api/v1/history?type=invalid&market_id={valid_uuid}")
    assert resp.status_code == 400


def test_get_history_returns_timeseries(client, mock_db):
    """GET /api/v1/history?type=funding&market_id=X → 200 with time-series array."""
    valid_uuid = str(uuid4())

    # Mock execute to return a Result-like iterable with tuples
    mock_result = MagicMock()
    mock_result.__iter__.return_value = iter([
        (datetime(2026, 1, 1, tzinfo=UTC), 0.0001),
        (datetime(2026, 1, 2, tzinfo=UTC), 0.0002),
    ])
    mock_db.execute.return_value = mock_result

    resp = client.get(f"/api/v1/history?type=funding&market_id={valid_uuid}")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert "observed_at" in data[0]
    assert "value" in data[0]


# ── 5. GET /looping ───────────────────────────────────────────────────────────


def test_get_looping_empty(client, mock_db):
    """GET /api/v1/looping with no snapshots → 200, empty array."""
    resp = client.get("/api/v1/looping")
    assert resp.status_code == 200
    assert resp.json() == []


def _loop_calc_row():
    """A pre-persisted LoopCalculation row (so the API uses stored results)."""
    return SimpleNamespace(
        id=str(uuid4()),
        lending_snapshot_id=MOCK_SNAPSHOT_ID,
        calc_version="loop-v1",
        input_capital=10000.0,
        input_target_ltv=0.7,
        input_safety_buffer=0.95,
        input_max_loops=20,
        deposited_capital=26000.0,
        borrowed_capital=16000.0,
        net_apy=12.5,
        effective_yield=12.5,
        leverage=2.6,
        safety_margin=0.15,
        liquidation_distance=18.0,
        risk_score=6.0,
    )


def test_get_looping_returns_opportunities(client, mock_db):
    """GET /api/v1/looping → 200 with populated opportunity (happy path)."""
    snap = SimpleNamespace(
        id=MOCK_SNAPSHOT_ID,
        market_id=MOCK_MARKET_ID,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        deposit_apy=5.0,
        borrow_apy=3.0,
        utilization=0.7,
        available_liquidity=1_000_000.0,
        total_supplied=5_000_000.0,
        total_borrowed=3_500_000.0,
        tvl=10_000_000.0,
        raw_payload=None,
    )
    market = SimpleNamespace(
        id=MOCK_MARKET_ID, protocol_id=MOCK_PROTOCOL_ID, asset="USDC", market_type="lending"
    )
    protocol = SimpleNamespace(
        id=MOCK_PROTOCOL_ID, name="Aave V3", type="lending", chain="ethereum", risk_score=0.5,
        deployed_at=None, audit_count=0,
    )
    calc = _loop_calc_row()

    snap_result = MagicMock()
    snap_result.scalars.return_value.all.return_value = [snap]
    mp_result = MagicMock()
    mp_result.all.return_value = [(market, protocol)]
    vol_result = MagicMock()
    vol_result.all.return_value = []
    calc_result = MagicMock()
    calc_result.scalars.return_value.all.return_value = [calc]
    # Loop fetch execute order: history -> depth -> deposit_vol.
    history_result = MagicMock()
    history_result.all.return_value = []
    depth_result = MagicMock()
    depth_result.all.return_value = []
    deposit_vol_result = MagicMock()
    deposit_vol_result.all.return_value = []

    mock_db.execute = AsyncMock(
        side_effect=[
            snap_result, mp_result, vol_result, calc_result,
            history_result, depth_result, deposit_vol_result,
        ]
    )

    resp = client.get("/api/v1/looping")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    opp = data[0]
    assert opp["asset"] == "USDC"
    assert opp["protocol"] == "Aave V3"
    assert opp["effective_yield"] == pytest.approx(12.5)
    assert "score" in opp
    assert "rank" in opp


# ── 6. GET /opportunities ─────────────────────────────────────────────────────


def test_get_opportunities_empty(client, mock_db):
    """GET /api/v1/opportunities with no data → 200, empty array."""
    resp = client.get("/api/v1/opportunities")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_opportunities_with_limit(client, mock_db):
    """GET /api/v1/opportunities?limit=5 → respects limit parameter."""
    resp = client.get("/api/v1/opportunities?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) <= 5


# ── Task-04: new fields, sort, sharpe, history ────────────────────────────────


def _loop_opportunity_mocks(snap=None, market=None, protocol=None, calc=None):
    """Return mock execute side-effects for one full _fetch_loop_opportunities call.

    Call order:
      1. snapshots (scalars)
      2. mp_rows (all)
      3. vol_map funding (all)       — existing volatility_penalty
      4. calc_result (scalars)
      5. history_result (all)        — get_yield_history
      6. depth_result (all)          — _history_depth_map (count, distinct_days)
      7. deposit_vol_result (all)    — _volatility_map_lending
    """
    snap = snap or SimpleNamespace(
        id=MOCK_SNAPSHOT_ID,
        market_id=MOCK_MARKET_ID,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        deposit_apy=5.0,
        borrow_apy=3.0,
        utilization=0.7,
        available_liquidity=1_000_000.0,
        total_supplied=5_000_000.0,
        total_borrowed=3_500_000.0,
        tvl=10_000_000.0,
        raw_payload=None,
    )
    market = market or SimpleNamespace(
        id=MOCK_MARKET_ID, protocol_id=MOCK_PROTOCOL_ID, asset="USDC", market_type="lending"
    )
    protocol = protocol or SimpleNamespace(
        id=MOCK_PROTOCOL_ID, name="Aave V3", type="lending", chain="ethereum", risk_score=0.5,
        # real confidence-signal fields (getattr-safe in routes if absent, but explicit here)
        deployed_at=None, audit_count=0,
    )
    calc = calc or _loop_calc_row()

    snap_result = MagicMock()
    snap_result.scalars.return_value.all.return_value = [snap]

    mp_result = MagicMock()
    mp_result.all.return_value = [(market, protocol)]

    vol_result = MagicMock()
    vol_result.all.return_value = []

    calc_result = MagicMock()
    calc_result.scalars.return_value.all.return_value = [calc]

    # get_yield_history returns one row: (market_id, today, yesterday, avg_7d, avg_30d)
    history_result = MagicMock()
    history_result.all.return_value = [
        (MOCK_MARKET_ID, 5.0, 4.8, 4.9, 4.7)
    ]

    # _history_depth_map: (market_id, count, distinct_days)
    depth_result = MagicMock()
    depth_result.all.return_value = [(MOCK_MARKET_ID, 20, 25)]

    # _volatility_map_lending: (market_id, stddev)
    deposit_vol_result = MagicMock()
    deposit_vol_result.all.return_value = [(MOCK_MARKET_ID, 0.5)]

    return [
        snap_result, mp_result, vol_result, calc_result,
        history_result, depth_result, deposit_vol_result,
    ]


def test_opportunities_response_includes_new_fields(client, mock_db):
    """GET /api/v1/opportunities items contain rating, breakdown, sharpe, history keys."""
    mock_db.execute = AsyncMock(side_effect=_loop_opportunity_mocks())

    resp = client.get("/api/v1/opportunities?type=loop")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    opp = data[0]

    # Task-04 required fields
    for key in ("rating", "rating_label", "confidence", "breakdown", "weights", "sharpe", "history"):
        assert key in opp, f"missing key: {key}"

    assert isinstance(opp["breakdown"], dict)
    assert isinstance(opp["weights"], dict)
    assert isinstance(opp["history"], dict)


def test_opportunities_rating_label_consistency(client, mock_db):
    """Top-ranked item's rating >= others; label matches rating thresholds."""
    mock_db.execute = AsyncMock(side_effect=_loop_opportunity_mocks())

    resp = client.get("/api/v1/opportunities?type=loop")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    opp = data[0]

    rating = opp["rating"]
    label = opp["rating_label"]

    # Single-item list → rating == 100 (min-max with one element)
    assert rating == pytest.approx(100.0)

    # Label must match threshold
    assert label == "Excellent"  # 100 >= 85


def test_opportunities_sharpe_null_on_zero_volatility(client, mock_db):
    """Market with zero deposit volatility → sharpe: null, not an error."""
    mocks = _loop_opportunity_mocks()
    # Override deposit_vol_result (now index 6) to return zero volatility.
    zero_vol = MagicMock()
    zero_vol.all.return_value = [(MOCK_MARKET_ID, 0.0)]
    mocks[6] = zero_vol

    mock_db.execute = AsyncMock(side_effect=mocks)

    resp = client.get("/api/v1/opportunities?type=loop")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["sharpe"] is None


def test_opportunities_sort_by_confidence(client, mock_db):
    """?sort=confidence orders results by confidence desc (no error)."""
    mock_db.execute = AsyncMock(side_effect=_loop_opportunity_mocks())

    resp = client.get("/api/v1/opportunities?type=loop&sort=confidence")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    # All items must have confidence
    for item in data:
        assert "confidence" in item


def test_opportunities_sort_bogus_returns_400(client, mock_db):
    """?sort=bogus → 400."""
    resp = client.get("/api/v1/opportunities?type=loop&sort=bogus")
    assert resp.status_code == 400


def test_opportunities_history_keys_present(client, mock_db):
    """Each item's history has today/yesterday/avg_7d/avg_30d keys."""
    mock_db.execute = AsyncMock(side_effect=_loop_opportunity_mocks())

    resp = client.get("/api/v1/opportunities?type=loop")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    hist = data[0]["history"]
    for key in ("today", "yesterday", "avg_7d", "avg_30d"):
        assert key in hist, f"missing history key: {key}"


# ── 7. Carry opps with no matching lending market are filtered (no real borrow leg) ─


def _carry_opportunity_mocks_no_lending():
    """Mock execute side-effects for _fetch_carry_opportunities where the funding
    asset has NO lending market → must be filtered, not modeled at 0% borrow.

    Carry fetch execute order when all opps are filtered (early return):
      1. funding snapshots (scalars)
      2. mp_rows (all)                  — (Market, Protocol)
      3. latest_lending_by_asset (all)  — (LendingSnapshot, asset)  ← EMPTY
      4. calcs (scalars)
      5. vol_map (all)                  — _volatility_map (pre-loop)
    """
    snap = SimpleNamespace(
        id=str(uuid4()),
        market_id=MOCK_MARKET_ID,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        funding_rate=0.0001,
        funding_interval_hours=1.0,
        annualized_funding=8.76,
        open_interest=1_000_000.0,
        volume_24h=50_000_000.0,
        long_short_ratio=1.5,
        mark_price=100.0,
        index_price=100.1,
        raw_payload=None,
    )
    market = SimpleNamespace(
        id=MOCK_MARKET_ID, protocol_id=MOCK_PROTOCOL_ID, asset="BTC", market_type="perp"
    )
    protocol = SimpleNamespace(
        id=MOCK_PROTOCOL_ID, name="Hyperliquid", type="derivatives", chain="hyperliquid",
        risk_score=0.3, deployed_at=None, audit_count=0,
    )

    snap_result = MagicMock()
    snap_result.scalars.return_value.all.return_value = [snap]

    mp_result = MagicMock()
    mp_result.all.return_value = [(market, protocol)]

    # _latest_lending_by_asset returns NO entry for "BTC" → no borrow leg.
    lend_result = MagicMock()
    lend_result.all.return_value = []

    calc_result = MagicMock()
    calc_result.scalars.return_value.all.return_value = []

    vol_result = MagicMock()
    vol_result.all.return_value = []

    return [snap_result, mp_result, lend_result, calc_result, vol_result]


def test_carry_opp_with_no_lending_market_is_filtered(client, mock_db):
    """A perp asset with no matching lending market must not appear as a carry opp.

    Regression: silently modeling a 0% borrow leg overstated net_carry for
    assets the configured lending collectors don't cover (e.g. BTC perps with
    only Aave USDC/USDT/DAI/WETH/wstETH lending). Now filtered at the source.
    """
    mock_db.execute = AsyncMock(side_effect=_carry_opportunity_mocks_no_lending())

    resp = client.get("/api/v1/opportunities?type=carry")
    assert resp.status_code == 200
    assert resp.json() == []


def _carry_opportunity_mocks_with_lending():
    """Mock execute side-effects for _fetch_carry_opportunities where the funding
    asset HAS a lending market → must be returned with the real borrow_cost.

    Carry fetch execute order (full path, one opp survives):
      1. funding snapshots (scalars)
      2. mp_rows (all)
      3. latest_lending_by_asset (all)  — (LendingSnapshot, asset)  ← NON-EMPTY
      4. calcs (scalars)
      5. vol_map (all)
      6. history (all)                  — get_yield_history
      7. depth (all)                    — _history_depth_map
    """
    snap = SimpleNamespace(
        id=str(uuid4()),
        market_id=MOCK_MARKET_ID,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        funding_rate=0.0001,
        funding_interval_hours=1.0,
        annualized_funding=8.76,
        open_interest=1_000_000.0,
        volume_24h=50_000_000.0,
        long_short_ratio=1.5,
        mark_price=100.0,
        index_price=100.1,
        raw_payload=None,
    )
    market = SimpleNamespace(
        id=MOCK_MARKET_ID, protocol_id=MOCK_PROTOCOL_ID, asset="USDC", market_type="perp"
    )
    protocol = SimpleNamespace(
        id=MOCK_PROTOCOL_ID, name="Hyperliquid", type="derivatives", chain="hyperliquid",
        risk_score=0.3, deployed_at=None, audit_count=0,
    )
    lend_snap = SimpleNamespace(
        id=str(uuid4()),
        market_id=str(uuid4()),
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        deposit_apy=5.0,
        borrow_apy=3.0,
        utilization=0.7,
        available_liquidity=1_000_000.0,
        total_supplied=5_000_000.0,
        total_borrowed=3_500_000.0,
        tvl=10_000_000.0,
        raw_payload=None,
    )

    snap_result = MagicMock()
    snap_result.scalars.return_value.all.return_value = [snap]

    mp_result = MagicMock()
    mp_result.all.return_value = [(market, protocol)]

    # _latest_lending_by_asset returns (LendingSnapshot, asset) for "USDC".
    lend_result = MagicMock()
    lend_result.all.return_value = [(lend_snap, "USDC")]

    calc_result = MagicMock()
    calc_result.scalars.return_value.all.return_value = []

    vol_result = MagicMock()
    vol_result.all.return_value = []

    history_result = MagicMock()
    history_result.all.return_value = []

    depth_result = MagicMock()
    depth_result.all.return_value = []

    return [
        snap_result, mp_result, lend_result, calc_result,
        vol_result, history_result, depth_result,
    ]


def test_carry_opp_with_lending_market_kept_and_borrows_real_cost(client, mock_db):
    """A perp asset with a matching lending market is kept and carries the real
    borrow_apy from that lending snapshot — not a 0% fallback."""
    mock_db.execute = AsyncMock(side_effect=_carry_opportunity_mocks_with_lending())

    resp = client.get("/api/v1/opportunities?type=carry")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    opp = data[0]
    # Real borrow_apy 3.0 from the lending snapshot, not the 0.0 fallback.
    assert opp["borrow_cost"] == pytest.approx(3.0)
    assert opp["spot_yield"] == pytest.approx(5.0)


# ── 8. Loop opps with inverted nominal spread are filtered (no real edge) ────


def _loop_opportunity_mocks_inverted(snap=None, market=None, protocol=None, calc=None):
    """Variant of _loop_opportunity_mocks where deposit < borrow: scanner must
    not surface the opp no matter how leverage turns the post-leverage number
    positive. Overrides only the snapshot's APY fields; rest inherits defaults."""
    mocks = _loop_opportunity_mocks(snap=snap, market=market, protocol=protocol, calc=calc)
    # Patch the snapshot (first side-effect, first scalars().all() payload) to be
    # inverted: borrow > deposit. Existing default calc still has positive
    # effective_yield — proving we filter off the nominal spread, NOT off the
    # post-leverage effective_yield (the whole point of this regression).
    inverted = SimpleNamespace(
        id=MOCK_SNAPSHOT_ID,
        market_id=MOCK_MARKET_ID,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        deposit_apy=3.19,   # < borrow_apy
        borrow_apy=3.93,
        utilization=0.7,
        available_liquidity=1_000_000.0,
        total_supplied=5_000_000.0,
        total_borrowed=3_500_000.0,
        tvl=10_000_000.0,
        raw_payload=None,
    )
    mocks[0].scalars.return_value.all.return_value = [inverted]
    return mocks


def test_loop_opp_with_inverted_nominal_spread_is_filtered(client, mock_db):
    """Loop with deposit < borrow must NOT surface — leverage manufacturing yield
    from an inverted nominal spread isn't an economically attractive opp, even
    when simulate_looping reports a positive effective_yield.

    Regression baseline: the /opportunities?type=loop route already had a
    `min_yield >= 0` filter, but it tested the post-leverage number. This test
    pins the pre-leverage nominal-spread filter.
    """
    mock_db.execute = AsyncMock(side_effect=_loop_opportunity_mocks_inverted())

    resp = client.get("/api/v1/opportunities?type=loop")
    assert resp.status_code == 200
    assert resp.json() == []


def test_loop_opp_with_flat_zero_spread_is_kept(client, mock_db):
    """A loop with deposit == borrow (zero nominal spread) is kept — the floor
    is non-negative, not strictly positive."""
    mocks = _loop_opportunity_mocks_inverted()
    # Equal rates, not inverted.
    flat = SimpleNamespace(
        id=MOCK_SNAPSHOT_ID,
        market_id=MOCK_MARKET_ID,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        deposit_apy=4.0,
        borrow_apy=4.0,
        utilization=0.7,
        available_liquidity=1_000_000.0,
        total_supplied=5_000_000.0,
        total_borrowed=3_500_000.0,
        tvl=10_000_000.0,
        raw_payload=None,
    )
    mocks[0].scalars.return_value.all.return_value = [flat]
    mock_db.execute = AsyncMock(side_effect=mocks)

    resp = client.get("/api/v1/opportunities?type=loop")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
