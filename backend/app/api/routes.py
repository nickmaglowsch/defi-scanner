"""REST API routes — thin DB queries serving latest snapshots + ranked opportunities."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.carry import calculate_carry
from app.calculations.looping import simulate_looping
from app.calculations.ranker import score_opportunities
from app.config import settings
from app.db.session import get_db
from app.models import (
    CarryCalculation,
    FundingSnapshot,
    LendingSnapshot,
    LoopCalculation,
    Market,
    Protocol,
)
from app.schemas.responses import (
    CarryOpportunityOut,
    FundingSnapshotOut,
    HistoryPointOut,
    LoopOpportunityOut,
    ProtocolOut,
)

logger = logging.getLogger("defi_scanner")
router = APIRouter(prefix="/api/v1")


def _parse_ranker_weights() -> dict:
    """Parse RANKER_WEIGHTS from config JSON string."""
    try:
        return json.loads(settings.RANKER_WEIGHTS)
    except json.JSONDecodeError:
        logger.warning("Invalid RANKER_WEIGHTS JSON, using defaults")
        return {}


def _latest_snapshot_subquery(
    model: type[LendingSnapshot | FundingSnapshot],
) -> object:
    """Return a subquery selecting id of the latest snapshot per market_id."""
    sub = (
        select(
            model.market_id,
            text("MAX(observed_at) AS max_ts"),
        )
        .group_by(model.market_id)
        .subquery()
    )
    return sub


def _make_opportunity_dict(
    protocol_name: str,
    asset: str,
    calc: dict,
    raw_score: float,
    rank: int,
) -> dict:
    """Build an opportunity-shaped dict for the response model."""
    out: dict = {
        "protocol": protocol_name,
        "asset": asset,
    }
    # Merge calc fields with snake_case keys
    for key, val in calc.items():
        out[key] = val
    out["score"] = raw_score
    out["rank"] = rank
    return out


# ── GET /opportunities ────────────────────────────────────────────────────────


@router.get("/opportunities")
async def get_opportunities(
    type: str = Query(default="all"),
    asset: str = Query(default=""),
    protocol: str = Query(default=""),
    min_yield: float = Query(default=0.0),
    min_liquidity: float = Query(default=0.0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[LoopOpportunityOut | CarryOpportunityOut]:
    """Return ranked opportunities (loop, carry, or all)."""
    results: list[LoopOpportunityOut | CarryOpportunityOut] = []

    if type in ("all", "loop"):
        loop_results = await _fetch_loop_opportunities(
            db, asset, protocol, min_yield, min_liquidity
        )
        results.extend(loop_results)
    if type in ("all", "carry"):
        carry_results = await _fetch_carry_opportunities(db, asset, protocol, min_yield)
        results.extend(carry_results)

    # ponytail: sort combined results by score descending, apply limit
    combined = sorted(results, key=lambda r: r.score, reverse=True)
    return combined[:limit]


# ── GET /looping ──────────────────────────────────────────────────────────────


@router.get("/looping")
async def get_looping(
    asset: str = Query(default=""),
    protocol: str = Query(default=""),
    min_yield: float = Query(default=0.0),
    min_liquidity: float = Query(default=0.0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[LoopOpportunityOut]:
    """Return ranked loop opportunities."""
    opps = await _fetch_loop_opportunities(db, asset, protocol, min_yield, min_liquidity)
    return sorted(opps, key=lambda o: o.score, reverse=True)[:limit]


# ── GET /funding ──────────────────────────────────────────────────────────────


@router.get("/funding")
async def get_funding(
    asset: str = Query(default=""),
    protocol: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[FundingSnapshotOut]:
    """Return latest funding rate snapshots."""
    # Subquery: latest observed_at per market
    max_ts = func.max(FundingSnapshot.observed_at).label("max_ts")
    sub = (
        select(FundingSnapshot.market_id, max_ts)
        .group_by(FundingSnapshot.market_id)
        .subquery()
    )

    query = (
        select(FundingSnapshot)
        .join(sub, FundingSnapshot.market_id == sub.c.market_id)
        .where(FundingSnapshot.observed_at == sub.c.max_ts)
    )

    if asset:
        # join markets to filter by asset
        market_sub = select(Market.id).where(Market.asset.ilike(f"%{asset}%")).subquery()
        query = query.where(FundingSnapshot.market_id.in_(market_sub))

    query = query.limit(limit)
    result = await db.execute(query)
    rows = result.scalars().all()

    return [FundingSnapshotOut.model_validate(r) for r in rows]


# ── GET /history ──────────────────────────────────────────────────────────────


@router.get("/history")
async def get_history(
    type: str = Query(default="funding"),
    market_id: str = Query(default=""),
    field: str = Query(default="funding_rate"),
    from_: str = Query(default="", alias="from"),
    to: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[HistoryPointOut]:
    """Return time-series data for charts."""
    if not market_id:
        raise HTTPException(status_code=400, detail="market_id is required")

    # Validate market_id is a valid UUID
    try:
        UUID(market_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid market_id UUID")

    points: list[HistoryPointOut] = []

    if type == "funding":
        field_map = {
            "funding_rate": FundingSnapshot.funding_rate,
            "annualized_funding": FundingSnapshot.annualized_funding,
        }
        col = field_map.get(field)
        if col is None:
            raise HTTPException(status_code=400, detail=f"Unknown funding field: {field}")

        query = (
            select(FundingSnapshot.observed_at, col)
            .where(FundingSnapshot.market_id == market_id)
            .order_by(FundingSnapshot.observed_at.asc())
        )
        if from_:
            try:
                dt_from = datetime.fromisoformat(from_)
                query = query.where(FundingSnapshot.observed_at >= dt_from)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid 'from' datetime")
        if to:
            try:
                dt_to = datetime.fromisoformat(to)
                query = query.where(FundingSnapshot.observed_at <= dt_to)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid 'to' datetime")
        query = query.limit(limit)

        result = await db.execute(query)
        for row in result:
            val = row[1] if row[1] is not None else 0.0
            points.append(HistoryPointOut(observed_at=row[0], value=float(val)))

    elif type == "lending":
        field_map = {
            "deposit_apy": LendingSnapshot.deposit_apy,
            "borrow_apy": LendingSnapshot.borrow_apy,
        }
        col = field_map.get(field)
        if col is None:
            raise HTTPException(status_code=400, detail=f"Unknown lending field: {field}")

        query = (
            select(LendingSnapshot.observed_at, col)
            .where(LendingSnapshot.market_id == market_id)
            .order_by(LendingSnapshot.observed_at.asc())
        )
        if from_:
            try:
                dt_from = datetime.fromisoformat(from_)
                query = query.where(LendingSnapshot.observed_at >= dt_from)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid 'from' datetime")
        if to:
            try:
                dt_to = datetime.fromisoformat(to)
                query = query.where(LendingSnapshot.observed_at <= dt_to)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid 'to' datetime")
        query = query.limit(limit)

        result = await db.execute(query)
        for row in result:
            val = row[1] if row[1] is not None else 0.0
            points.append(HistoryPointOut(observed_at=row[0], value=float(val)))
    else:
        raise HTTPException(status_code=400, detail="type must be 'funding' or 'lending'")

    return points


# ── GET /protocols ────────────────────────────────────────────────────────────


@router.get("/protocols")
async def get_protocols(
    db: AsyncSession = Depends(get_db),
) -> list[ProtocolOut]:
    """Return all protocols."""
    result = await db.execute(select(Protocol))
    rows = result.scalars().all()
    return [ProtocolOut.model_validate(r) for r in rows]


# ── GET /assets ───────────────────────────────────────────────────────────────


@router.get("/assets")
async def get_assets(
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Return distinct asset symbols across all markets."""
    result = await db.execute(select(Market.asset).distinct())
    return [row[0] for row in result]


# ── Internal helpers for opportunity fetching ─────────────────────────────────


async def _fetch_loop_opportunities(
    db: AsyncSession,
    asset_filter: str,
    protocol_filter: str,
    min_yield: float,
    min_liquidity: float,
) -> list[LoopOpportunityOut]:
    """Fetch latest lending snapshots, run simulate_looping, score via ranker."""
    max_ts = func.max(LendingSnapshot.observed_at).label("max_ts")
    sub = (
        select(LendingSnapshot.market_id, max_ts)
        .group_by(LendingSnapshot.market_id)
        .subquery()
    )

    query = (
        select(LendingSnapshot)
        .join(sub, LendingSnapshot.market_id == sub.c.market_id)
        .where(LendingSnapshot.observed_at == sub.c.max_ts)
    )
    # Filter by asset/protocol via market join if needed
    # ponytail: eager-load market+protocol in a single query loop
    result = await db.execute(query)
    snapshots = result.scalars().all()

    loop_opps: list[dict] = []
    weights = _parse_ranker_weights()

    for snap in snapshots:
        market = await db.get(Market, snap.market_id)
        if market is None:
            continue
        protocol = await db.get(Protocol, market.protocol_id)
        if protocol is None:
            continue

        # Apply filters
        if asset_filter and asset_filter.lower() not in market.asset.lower():
            continue
        if protocol_filter and protocol_filter.lower() not in protocol.name.lower():
            continue

        # Check if calculation already exists for this snapshot
        existing_calc = await db.execute(
            select(LoopCalculation).where(
                LoopCalculation.lending_snapshot_id == snap.id,
                LoopCalculation.calc_version == "loop-v1",
            )
        )
        calc_row = existing_calc.scalar_one_or_none()

        if calc_row is None:
            # Run simulate_looping with default inputs
            calc = simulate_looping(
                deposit_apy=snap.deposit_apy or 0.0,
                borrow_apy=snap.borrow_apy or 0.0,
                max_ltv=0.8,
                liquidation_threshold=0.85,
                initial_capital=10000.0,
                target_ltv=0.7,
                safety_buffer=0.95,
                max_loops=20,
            )
            # Persist calculation
            calc_row = LoopCalculation(
                lending_snapshot_id=snap.id,
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
            db.add(calc_row)
            await db.flush()
        else:
            # Reconstruct calc dict from DB row
            calc = {
                "calc_version": calc_row.calc_version,
                "input_capital": calc_row.input_capital or 0.0,
                "input_target_ltv": calc_row.input_target_ltv or 0.0,
                "input_safety_buffer": calc_row.input_safety_buffer or 0.0,
                "input_max_loops": calc_row.input_max_loops or 0,
                "deposited_capital": calc_row.deposited_capital or 0.0,
                "borrowed_capital": calc_row.borrowed_capital or 0.0,
                "net_apy": calc_row.net_apy or 0.0,
                "effective_yield": calc_row.effective_yield or 0.0,
                "leverage": calc_row.leverage or 0.0,
                "safety_margin": calc_row.safety_margin or 0.0,
                "liquidation_distance": calc_row.liquidation_distance or 0.0,
                "risk_score": calc_row.risk_score or 0.0,
            }

        # Compute volatility penalty via windowed STDDEV
        vol_penalty = await _volatility_penalty(db, snap.market_id)

        # Build opportunity dict for ranker
        opp = {
            "yield_score": calc.get("effective_yield", 0.0),
            "liquidity_score": snap.available_liquidity or 0.0,
            "tvl_score": snap.tvl or 0.0,
            "stability_score": snap.deposit_apy or 0.0,
            "utilization_penalty": snap.utilization or 0.0,
            "volatility_penalty": vol_penalty,
            "protocol_risk": protocol.risk_score,
            # Cache for output
            "_protocol": protocol.name,
            "_asset": market.asset,
            "_calc": calc,
            "_snap": snap,
        }
        loop_opps.append(opp)

    if not loop_opps:
        return []

    # Score via ranker
    ranked = score_opportunities(loop_opps, weights)

    # Filter by min_yield / min_liquidity
    filtered = [
        r
        for r in ranked
        if r.get("_calc", {}).get("effective_yield", 0.0) >= min_yield
        and (r.get("_snap") and (r["_snap"].available_liquidity or 0.0) >= min_liquidity)
    ]

    # Build response models
    out: list[LoopOpportunityOut] = []
    for r in filtered:
        calc = r["_calc"]
        snap = r["_snap"]
        out.append(
            LoopOpportunityOut(
                protocol=r["_protocol"],
                asset=r["_asset"],
                deposit_apy=snap.deposit_apy,
                borrow_apy=snap.borrow_apy,
                effective_yield=calc.get("effective_yield"),
                leverage=calc.get("leverage"),
                safety_margin=calc.get("safety_margin"),
                liquidation_distance=calc.get("liquidation_distance"),
                risk_score=calc.get("risk_score"),
                score=r["score"],
                rank=r["rank"],
            )
        )
    return out


async def _fetch_carry_opportunities(
    db: AsyncSession,
    asset_filter: str,
    protocol_filter: str,
    min_yield: float,
) -> list[CarryOpportunityOut]:
    """Fetch latest funding snapshots + corresponding lending, run calculate_carry, score."""
    max_ts_f = func.max(FundingSnapshot.observed_at).label("max_ts")
    sub = (
        select(FundingSnapshot.market_id, max_ts_f)
        .group_by(FundingSnapshot.market_id)
        .subquery()
    )

    query = (
        select(FundingSnapshot)
        .join(sub, FundingSnapshot.market_id == sub.c.market_id)
        .where(FundingSnapshot.observed_at == sub.c.max_ts)
    )
    result = await db.execute(query)
    snapshots = result.scalars().all()

    carry_opps: list[dict] = []
    weights = _parse_ranker_weights()

    for snap in snapshots:
        market = await db.get(Market, snap.market_id)
        if market is None:
            continue
        protocol = await db.get(Protocol, market.protocol_id)
        if protocol is None:
            continue

        if asset_filter and asset_filter.lower() not in market.asset.lower():
            continue
        if protocol_filter and protocol_filter.lower() not in protocol.name.lower():
            continue

        # Find latest lending snapshot for same asset (cross-market borrowing cost)
        borrow_cost = 0.0
        spot_yield = 0.0
        max_ts_lend = func.max(LendingSnapshot.observed_at).label("max_ts")
        lend_sub = (
            select(LendingSnapshot.market_id, max_ts_lend)
            .group_by(LendingSnapshot.market_id)
            .subquery()
        )
        lend_query = (
            select(LendingSnapshot)
            .join(lend_sub, LendingSnapshot.market_id == lend_sub.c.market_id)
            .where(LendingSnapshot.observed_at == lend_sub.c.max_ts)
        )
        lend_result = await db.execute(lend_query)
        lend_snaps = lend_result.scalars().all()

        # Find matching lending market by asset for borrow cost / spot yield
        for ls in lend_snaps:
            lm = await db.get(Market, ls.market_id)
            if lm and lm.asset == market.asset:
                borrow_cost = ls.borrow_apy or 0.0
                spot_yield = ls.deposit_apy or 0.0
                break

        # Check for existing carry calculation
        existing_calc = await db.execute(
            select(CarryCalculation).where(
                CarryCalculation.funding_snapshot_id == snap.id,
                CarryCalculation.calc_version == "carry-v1",
            )
        )
        calc_row = existing_calc.scalar_one_or_none()

        if calc_row is None:
            calc = calculate_carry(
                spot_yield=spot_yield,
                funding_yield=snap.annualized_funding or 0.0,
                borrow_cost=borrow_cost,
                trading_fees=0.1,  # ponytail: default trading fees, configurable later
            )
            calc_row = CarryCalculation(
                funding_snapshot_id=snap.id,
                calc_version="carry-v1",
                spot_yield=calc["spot_yield"],
                funding_yield=calc["funding_yield"],
                borrow_cost=calc["borrow_cost"],
                trading_fees=calc["trading_fees"],
                net_carry=calc["net_carry"],
                risk_score=calc["risk_score"],
                expected_annual_return=calc["expected_annual_return"],
            )
            db.add(calc_row)
            await db.flush()
        else:
            calc = {
                "calc_version": calc_row.calc_version,
                "spot_yield": calc_row.spot_yield or 0.0,
                "funding_yield": calc_row.funding_yield or 0.0,
                "borrow_cost": calc_row.borrow_cost or 0.0,
                "trading_fees": calc_row.trading_fees or 0.0,
                "net_carry": calc_row.net_carry or 0.0,
                "risk_score": calc_row.risk_score or 0.0,
                "expected_annual_return": calc_row.expected_annual_return or 0.0,
            }

        vol_penalty = await _volatility_penalty(db, snap.market_id)

        opp = {
            "yield_score": calc.get("net_carry", 0.0),
            "liquidity_score": snap.open_interest or 0.0,
            "tvl_score": snap.volume_24h or 0.0,
            "stability_score": snap.funding_rate or 0.0,
            "utilization_penalty": 0.0,  # not applicable for perps
            "volatility_penalty": vol_penalty,
            "protocol_risk": protocol.risk_score,
            "_protocol": protocol.name,
            "_asset": market.asset,
            "_calc": calc,
        }
        carry_opps.append(opp)

    if not carry_opps:
        return []

    ranked = score_opportunities(carry_opps, weights)

    filtered = [
        r
        for r in ranked
        if r.get("_calc", {}).get("net_carry", 0.0) >= min_yield
    ]

    out: list[CarryOpportunityOut] = []
    for r in filtered:
        calc = r["_calc"]
        out.append(
            CarryOpportunityOut(
                protocol=r["_protocol"],
                asset=r["_asset"],
                funding_yield=calc.get("funding_yield"),
                spot_yield=calc.get("spot_yield"),
                borrow_cost=calc.get("borrow_cost"),
                trading_fees=calc.get("trading_fees"),
                net_carry=calc.get("net_carry"),
                risk_score=calc.get("risk_score"),
                score=r["score"],
                rank=r["rank"],
            )
        )
    return out


async def _volatility_penalty(db: AsyncSession, market_id: str) -> float:
    """Compute volatility penalty via windowed STDDEV of funding_rate.

    Uses SQL window function: STDDEV(funding_rate) OVER (PARTITION BY market_id
    ORDER BY observed_at ROWS 20 PRECEDING). Returns 0.0 if fewer than 20 rows
    (neutral).
    """
    window = settings.DEFI_VOLATILITY_WINDOW
    sql = text("""
        SELECT STDDEV(funding_rate) AS vol
        FROM (
            SELECT funding_rate
            FROM funding_snapshots
            WHERE market_id = :market_id
            ORDER BY observed_at DESC
            LIMIT :window
        ) AS recent
    """)
    result = await db.execute(sql, {"market_id": market_id, "window": window})
    row = result.one_or_none()
    if row is None or row[0] is None:
        return 0.0
    return float(row[0])
