"""Calculation orchestrator — run by collectors after snapshot writes.

ponytail: one function per snapshot type, called inline from the collector
after the snapshot is flushed. No separate background task needed.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.carry import calculate_carry
from app.calculations.cross_protocol import calculate_cross_protocol_spread
from app.calculations.looping import simulate_looping
from app.models import (
    CarryCalculation,
    CrossProtocolCalculation,
    FundingSnapshot,
    LendingSnapshot,
    LoopCalculation,
    Market,
    Protocol,
)

logger = logging.getLogger("defi_scanner")

# Conservative fallbacks used when a reserve's on-chain config is missing.
_DEFAULT_MAX_LTV = 0.8
_DEFAULT_LIQ_THRESHOLD = 0.85


def ltv_params_from_snapshot(snapshot: LendingSnapshot) -> tuple[float, float]:
    """Extract (max_ltv, liquidation_threshold) as fractions from a snapshot's raw_payload.

    The Aave adapter persists these as percentages (e.g. 80.0 = 80% LTV) under
    raw_payload.configuration. Falls back to conservative defaults when absent.
    """
    raw = snapshot.raw_payload or {}
    config = raw.get("configuration", {}) if isinstance(raw, dict) else {}
    ltv_pct = config.get("ltv_pct")
    liq_pct = config.get("liquidation_threshold_pct")
    max_ltv = (float(ltv_pct) / 100.0) if isinstance(ltv_pct, (int, float)) else _DEFAULT_MAX_LTV
    liq = (float(liq_pct) / 100.0) if isinstance(liq_pct, (int, float)) else _DEFAULT_LIQ_THRESHOLD
    return max_ltv, liq


# Market types that have no borrow leg — loop simulation is meaningless for these.
_NO_BORROW_LEG_MARKET_TYPES = frozenset({"staking", "restaking", "pendle", "stable_lending"})


async def trigger_loop_calculation(session: AsyncSession, snapshot: LendingSnapshot) -> None:
    """Run simulate_looping on a fresh lending snapshot and persist the result.

    Idempotent: skips if a LoopCalculation already exists for this
    snapshot_id with calc_version 'loop-v1'.
    Skips market types with no borrow leg (staking, restaking, pendle, stable_lending).
    """
    existing = await session.execute(
        select(LoopCalculation).where(
            LoopCalculation.lending_snapshot_id == snapshot.id,
            LoopCalculation.calc_version == "loop-v1",
        )
    )
    if existing.scalar_one_or_none() is not None:
        return

    market = await session.get(Market, snapshot.market_id)
    if market is None:
        return

    # ponytail: skip loop simulation for no-borrow-leg market types
    if market.market_type in _NO_BORROW_LEG_MARKET_TYPES:
        logger.debug(
            "Skipping loop calculation for market %s (market_type=%s has no borrow leg)",
            market.id,
            market.market_type,
        )
        return

    max_ltv, liq_threshold = ltv_params_from_snapshot(snapshot)

    calc = simulate_looping(
        deposit_apy=snapshot.deposit_apy or 0.0,
        borrow_apy=snapshot.borrow_apy or 0.0,
        max_ltv=max_ltv,
        liquidation_threshold=liq_threshold,
        initial_capital=10000.0,
        target_ltv=0.7,
        safety_buffer=0.95,
        max_loops=20,
    )

    row = LoopCalculation(
        lending_snapshot_id=snapshot.id,
        calc_version="loop-v1",
        input_capital=calc["input_capital"],
        input_target_ltv=calc["input_target_ltv"],
        input_safety_buffer=calc["input_safety_buffer"],
        input_max_loops=calc["input_max_loops"],
        deposited_capital=calc["deposited_capital"],
        borrowed_capital=calc["borrowed_capital"],
        net_apy=calc["net_apy"],
        effective_yield=calc["effective_yield"],
        leverage=calc["leverage"],
        safety_margin=calc["safety_margin"],
        liquidation_distance=calc["liquidation_distance"],
        risk_score=calc["risk_score"],
    )
    session.add(row)
    logger.debug("Loop calculation persisted for snapshot %s", snapshot.id)


async def trigger_carry_calculation(session: AsyncSession, snapshot: FundingSnapshot) -> None:
    """Run calculate_carry on a fresh funding snapshot and persist the result.

    Idempotent: skips if a CarryCalculation already exists for this
    snapshot_id with calc_version 'carry-v1'.
    Tries to find a matching lending snapshot for spot_yield / borrow_cost.
    """
    existing = await session.execute(
        select(CarryCalculation).where(
            CarryCalculation.funding_snapshot_id == snapshot.id,
            CarryCalculation.calc_version == "carry-v1",
        )
    )
    if existing.scalar_one_or_none() is not None:
        return

    market = await session.get(Market, snapshot.market_id)
    if market is None:
        return

    # Find latest lending snapshot for the same asset for borrow-cost / spot-yield
    borrow_cost = 0.0
    spot_yield = 0.0

    # ponytail: find any lending market with same asset
    market_q = select(Market.id).where(Market.asset == market.asset)
    m_result = await session.execute(market_q)
    matching_market_ids = [r[0] for r in m_result]

    if matching_market_ids:
        lend_q = (
            select(LendingSnapshot)
            .where(LendingSnapshot.market_id.in_(matching_market_ids))
            .order_by(LendingSnapshot.observed_at.desc())
            .limit(1)
        )
        lend_result = await session.execute(lend_q)
        lend_snap = lend_result.scalar_one_or_none()
        if lend_snap is not None:
            borrow_cost = lend_snap.borrow_apy or 0.0
            spot_yield = lend_snap.deposit_apy or 0.0

    calc = calculate_carry(
        spot_yield=spot_yield,
        funding_yield=snapshot.annualized_funding or 0.0,
        borrow_cost=borrow_cost,
        trading_fees=0.1,
    )

    row = CarryCalculation(
        funding_snapshot_id=snapshot.id,
        calc_version="carry-v1",
        spot_yield=calc["spot_yield"],
        funding_yield=calc["funding_yield"],
        borrow_cost=calc["borrow_cost"],
        trading_fees=calc["trading_fees"],
        net_carry=calc["net_carry"],
        risk_score=calc["risk_score"],
        expected_annual_return=calc["expected_annual_return"],
    )
    session.add(row)
    logger.debug("Carry calculation persisted for snapshot %s", snapshot.id)


async def trigger_cross_protocol_calculation(
    session: AsyncSession,
    snapshot: LendingSnapshot,
) -> None:
    """Find the best cross-protocol pair for the snapshot's asset and persist the result.

    Same-asset only (deposit on one protocol, borrow on another).
    Idempotent: skips if a CrossProtocolCalculation already exists for this
    (deposit_market_id, borrow_market_id) pair with calc_version 'cross-protocol-v1'.
    """
    market = await session.get(Market, snapshot.market_id)
    if market is None:
        return

    # Find all lending markets for the same asset on different protocols.
    same_asset_markets_q = (
        select(Market.id, Market.protocol_id)
        .where(Market.asset == market.asset, Market.id != market.id, Market.market_type == "lending")
    )
    result = await session.execute(same_asset_markets_q)
    other_markets = result.all()

    if not other_markets:
        return

    # Collect protocol names for risk scoring (cross-chain gets extra penalty).
    deposit_protocol = await session.get(Protocol, market.protocol_id)

    for other_market_id, other_protocol_id in other_markets:
        # Idempotency: skip if already computed.
        existing = await session.execute(
            select(CrossProtocolCalculation).where(
                CrossProtocolCalculation.deposit_market_id == snapshot.market_id,
                CrossProtocolCalculation.borrow_market_id == other_market_id,
                CrossProtocolCalculation.calc_version == "cross-protocol-v1",
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        # Get latest lending snapshot for the borrow market.
        borrow_snap_q = (
            select(LendingSnapshot)
            .where(LendingSnapshot.market_id == other_market_id)
            .order_by(LendingSnapshot.observed_at.desc())
            .limit(1)
        )
        borrow_snap_result = await session.execute(borrow_snap_q)
        borrow_snap = borrow_snap_result.scalar_one_or_none()
        if borrow_snap is None:
            continue

        max_ltv, liq_threshold = ltv_params_from_snapshot(snapshot)
        calc = calculate_cross_protocol_spread(
            deposit_apy=snapshot.deposit_apy or 0.0,
            borrow_apy=borrow_snap.borrow_apy or 0.0,
            max_ltv=max_ltv,
            liq_threshold=liq_threshold,
        )

        row = CrossProtocolCalculation(
            deposit_market_id=snapshot.market_id,
            borrow_market_id=other_market_id,
            calc_version="cross-protocol-v1",
            deposit_apy=snapshot.deposit_apy,
            borrow_apy=borrow_snap.borrow_apy,
            net_spread=calc["net_spread"],
            leverage=calc["leverage"],
            risk_score=calc["risk_score"],
            penalty_breakdown={"cross_protocol_penalty": 0.5},
        )
        session.add(row)
        logger.debug(
            "Cross-protocol calculation persisted: deposit=%s borrow=%s",
            snapshot.market_id,
            other_market_id,
        )
