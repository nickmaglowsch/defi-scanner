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
    """GET /api/v1/funding → 200 with populated list."""
    snap = _funding_snapshot_row()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [snap]
    mock_db.execute.return_value = mock_result

    resp = client.get("/api/v1/funding?limit=3")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1


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
