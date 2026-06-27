"""Orchestrator integration tests — verify calculations are triggered after snapshot writes.

Tests the trigger_* functions from app.calculations.orchestrator using mock DB sessions.
Verifies:
  - Loop calculation is triggered for lending snapshots
  - Carry calculation is triggered for funding snapshots
  - Cross-protocol calculation is triggered for lending snapshots with peer markets
  - Loop simulation is skipped for staking/restaking/pendle/stable_lending market types
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.calculations.orchestrator import (
    trigger_carry_calculation,
    trigger_cross_protocol_calculation,
    trigger_loop_calculation,
)
from app.models import (
    CarryCalculation,
    CrossProtocolCalculation,
    LoopCalculation,
)


# ── Helpers (SimpleNamespace avoids SQLAlchemy ORM machinery) ─────────────────


def _lending_snap(
    market_id: str,
    deposit_apy: float = 5.0,
    borrow_apy: float = 3.0,
    raw_payload: object = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=str(uuid4()),
        market_id=market_id,
        deposit_apy=deposit_apy,
        borrow_apy=borrow_apy,
        raw_payload=raw_payload,
    )


def _funding_snap(market_id: str, annualized_funding: float = 8.76) -> SimpleNamespace:
    return SimpleNamespace(
        id=str(uuid4()),
        market_id=market_id,
        annualized_funding=annualized_funding,
        funding_rate=0.0001,
        funding_interval_hours=1.0,
    )


def _market(market_id: str, market_type: str = "lending", asset: str = "USDC") -> SimpleNamespace:
    return SimpleNamespace(
        id=market_id,
        market_type=market_type,
        asset=asset,
        protocol_id=str(uuid4()),
    )


def _make_session(
    existing_calc: object = None,
    market: object = None,
) -> AsyncMock:
    """Build an AsyncMock session configured for orchestrator tests."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing_calc
    session.execute = AsyncMock(return_value=existing_result)
    session.get = AsyncMock(return_value=market)
    return session


# ── trigger_loop_calculation ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trigger_loop_calculation_inserts_row() -> None:
    """trigger_loop_calculation inserts a LoopCalculation row for a lending snapshot."""
    market_id = str(uuid4())
    snap = _lending_snap(market_id)
    market = _market(market_id, "lending")
    session = _make_session(market=market)

    await trigger_loop_calculation(session, snap)

    added = session.add.call_args_list
    assert len(added) == 1
    row = added[0].args[0]
    assert isinstance(row, LoopCalculation)
    assert row.lending_snapshot_id == snap.id
    assert row.calc_version == "loop-v1"
    assert row.net_apy is not None


@pytest.mark.asyncio
async def test_trigger_loop_calculation_idempotent() -> None:
    """trigger_loop_calculation skips if a LoopCalculation already exists."""
    market_id = str(uuid4())
    snap = _lending_snap(market_id)
    market = _market(market_id, "lending")
    existing = MagicMock(spec=LoopCalculation)
    session = _make_session(existing_calc=existing, market=market)

    await trigger_loop_calculation(session, snap)

    session.add.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "market_type",
    ["staking", "restaking", "pendle", "stable_lending"],
)
async def test_trigger_loop_skips_no_borrow_leg_market_types(market_type: str) -> None:
    """Loop simulation is skipped for market types with no borrow leg."""
    market_id = str(uuid4())
    snap = _lending_snap(market_id)
    market = _market(market_id, market_type)
    session = _make_session(market=market)

    await trigger_loop_calculation(session, snap)

    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_loop_skips_missing_market() -> None:
    """trigger_loop_calculation skips gracefully if market row is absent."""
    snap = _lending_snap(str(uuid4()))
    session = _make_session(market=None)

    await trigger_loop_calculation(session, snap)

    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_loop_uses_raw_payload_ltv() -> None:
    """trigger_loop_calculation uses LTV from raw_payload when present."""
    market_id = str(uuid4())
    raw = {"configuration": {"ltv_pct": 75.0, "liquidation_threshold_pct": 80.0}}
    snap = _lending_snap(market_id, raw_payload=raw)
    market = _market(market_id, "lending")
    session = _make_session(market=market)

    await trigger_loop_calculation(session, snap)

    added = session.add.call_args_list
    assert len(added) == 1
    row = added[0].args[0]
    assert isinstance(row, LoopCalculation)
    assert row.leverage >= 1.0


# ── trigger_carry_calculation ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trigger_carry_calculation_inserts_row() -> None:
    """trigger_carry_calculation inserts a CarryCalculation row for a funding snapshot."""
    market_id = str(uuid4())
    snap = _funding_snap(market_id)
    market = _market(market_id, "perp")

    session = AsyncMock()
    session.add = MagicMock()

    # execute calls:
    # 1. existing carry check → None
    # 2. matching market ids (select Market.id where asset=...) → empty
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = None

    empty_result = MagicMock()
    empty_result.__iter__ = MagicMock(return_value=iter([]))

    session.execute = AsyncMock(side_effect=[existing_result, empty_result])
    session.get = AsyncMock(return_value=market)

    await trigger_carry_calculation(session, snap)

    added = session.add.call_args_list
    assert len(added) == 1
    row = added[0].args[0]
    assert isinstance(row, CarryCalculation)
    assert row.calc_version == "carry-v1"
    assert row.funding_yield == pytest.approx(8.76)


@pytest.mark.asyncio
async def test_trigger_carry_calculation_idempotent() -> None:
    """trigger_carry_calculation skips if a CarryCalculation already exists."""
    market_id = str(uuid4())
    snap = _funding_snap(market_id)
    market = _market(market_id, "perp")
    existing = MagicMock(spec=CarryCalculation)

    session = AsyncMock()
    session.add = MagicMock()
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing
    session.execute = AsyncMock(return_value=existing_result)
    session.get = AsyncMock(return_value=market)

    await trigger_carry_calculation(session, snap)

    session.add.assert_not_called()


# ── trigger_cross_protocol_calculation ────────────────────────────────────────


@pytest.mark.asyncio
async def test_trigger_cross_protocol_skips_no_peer_markets() -> None:
    """trigger_cross_protocol_calculation skips when no same-asset peer markets exist."""
    market_id = str(uuid4())
    snap = _lending_snap(market_id)
    market = _market(market_id, "lending")

    session = AsyncMock()
    session.add = MagicMock()
    session.get = AsyncMock(return_value=market)

    empty_result = MagicMock()
    empty_result.all.return_value = []
    session.execute = AsyncMock(return_value=empty_result)

    await trigger_cross_protocol_calculation(session, snap)

    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_cross_protocol_inserts_row_with_peer_market() -> None:
    """trigger_cross_protocol_calculation inserts a CrossProtocolCalculation when a peer exists."""
    deposit_market_id = str(uuid4())
    borrow_market_id = str(uuid4())
    deposit_proto_id = str(uuid4())
    borrow_proto_id = str(uuid4())

    snap = _lending_snap(deposit_market_id, deposit_apy=5.0, borrow_apy=3.0)
    deposit_market = _market(deposit_market_id, "lending")
    deposit_market = SimpleNamespace(
        id=deposit_market_id,
        market_type="lending",
        asset="USDC",
        protocol_id=deposit_proto_id,
    )
    deposit_proto = SimpleNamespace(id=deposit_proto_id, name="Aave V3", chain="ethereum")

    borrow_snap = SimpleNamespace(
        id=str(uuid4()),
        market_id=borrow_market_id,
        borrow_apy=2.0,
        raw_payload=None,
    )

    session = AsyncMock()
    session.add = MagicMock()

    # get(Market, deposit_market_id) → deposit_market
    # get(Protocol, deposit_proto_id) → deposit_proto
    session.get = AsyncMock(side_effect=[deposit_market, deposit_proto])

    # execute calls:
    # 1. same_asset_markets → [(borrow_market_id, borrow_proto_id)]
    # 2. existing cross-protocol check → None
    # 3. latest borrow snapshot → borrow_snap
    peer_result = MagicMock()
    peer_result.all.return_value = [(borrow_market_id, borrow_proto_id)]

    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = None

    borrow_snap_result = MagicMock()
    borrow_snap_result.scalar_one_or_none.return_value = borrow_snap

    session.execute = AsyncMock(side_effect=[
        peer_result,
        existing_result,
        borrow_snap_result,
    ])

    await trigger_cross_protocol_calculation(session, snap)

    added = session.add.call_args_list
    assert len(added) == 1
    row = added[0].args[0]
    assert isinstance(row, CrossProtocolCalculation)
    assert row.deposit_market_id == deposit_market_id
    assert row.borrow_market_id == borrow_market_id
    assert row.calc_version == "cross-protocol-v1"
    assert row.net_spread == pytest.approx(3.0)  # deposit 5.0 - borrow 2.0
