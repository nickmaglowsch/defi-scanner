"""Calculation orchestrator — run by collectors after snapshot writes.

ponytail: one function per snapshot type, called inline from the collector
after the snapshot is flushed. No separate background task needed.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.carry import calculate_carry
from app.calculations.looping import simulate_looping
from app.models import (
    CarryCalculation,
    FundingSnapshot,
    LendingSnapshot,
    LoopCalculation,
    Market,
)

logger = logging.getLogger("defi_scanner")


async def trigger_loop_calculation(session: AsyncSession, snapshot: LendingSnapshot) -> None:
    """Run simulate_looping on a fresh lending snapshot and persist the result.

    Idempotent: skips if a LoopCalculation already exists for this
    snapshot_id with calc_version 'loop-v1'.
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

    calc = simulate_looping(
        deposit_apy=snapshot.deposit_apy or 0.0,
        borrow_apy=snapshot.borrow_apy or 0.0,
        max_ltv=0.8,
        liquidation_threshold=0.85,
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
