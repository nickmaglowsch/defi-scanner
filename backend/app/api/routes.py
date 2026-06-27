"""REST API routes — thin DB queries serving latest snapshots + ranked opportunities."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.carry import calculate_carry
from app.calculations.cross_protocol import calculate_cross_protocol_spread
from app.calculations.history_agg import get_historical_rank, get_percentile, get_yield_history
from app.calculations.looping import simulate_looping
from app.calculations.orchestrator import ltv_params_from_snapshot
from app.calculations.ranker import score_opportunities
from app.calculations.rating import rate_opportunities, rerate_combined
from app.config import settings
from app.db.session import get_db
from app.models import (
    CarryCalculation,
    CrossProtocolCalculation,
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
    OpportunityOut,
    ProtocolOut,
    YieldHistoryOut,
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


_VALID_SORTS = {"return", "risk", "confidence", "sharpe", "liquidity"}


@router.get("/opportunities")
async def get_opportunities(
    type: str = Query(default="all"),
    asset: str = Query(default=""),
    protocol: str = Query(default=""),
    min_yield: float = Query(default=0.0),
    min_liquidity: float = Query(default=0.0),
    limit: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="return"),
    db: AsyncSession = Depends(get_db),
) -> list[OpportunityOut]:
    """Return ranked opportunities (loop, carry, or all)."""
    _VALID_TYPES = {"all", "loop", "carry", "cross_protocol", "stable_lending", "staking", "restaking", "pendle"}
    if type not in _VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"type must be one of: {', '.join(sorted(_VALID_TYPES))}",
        )
    if sort not in _VALID_SORTS:
        raise HTTPException(
            status_code=400,
            detail=f"sort must be one of: {', '.join(sorted(_VALID_SORTS))}",
        )
    results: list[OpportunityOut] = []

    if type in ("all", "loop"):
        loop_results = await _fetch_loop_opportunities(
            db, asset, protocol, min_yield, min_liquidity
        )
        results.extend(loop_results)
    if type in ("all", "carry"):
        carry_results = await _fetch_carry_opportunities(db, asset, protocol, min_yield)
        results.extend(carry_results)
    if type in ("all", "cross_protocol"):
        cross_results = await _fetch_cross_protocol_opportunities(db, asset, protocol, min_yield)
        results.extend(cross_results)
    # ponytail: staking/restaking/pendle/stable_lending adapters stub NotImplementedError;
    # no snapshot rows exist yet. These types are valid — they return empty until
    # adapters are wired into the collector runner.
    if type in ("stable_lending", "staking", "restaking", "pendle"):
        results.extend(
            await _fetch_market_type_opportunities(db, type, asset, protocol, min_yield)
        )

    # type=all merged two independently-rated batches (loop + carry) with their own
    # min-max scales and medals — rerate on one shared scale so 🥇🥈🥉 are unique
    # and the 0-100 ratings are comparable across types.
    if type == "all":
        rerate_combined(results)

    # ponytail: sort key map — None values sort last (use -inf sentinel)
    _sort_key = {
        "return":     lambda r: r.score,
        "risk":       lambda r: -(r.risk_score or 0.0),  # lower risk first
        "confidence": lambda r: r.confidence or 0.0,
        "sharpe":     lambda r: r.sharpe if r.sharpe is not None else -1e9,
        "liquidity":  lambda r: r.score,  # ponytail: proxy until liquidity field exposed
    }
    combined = sorted(results, key=_sort_key[sort], reverse=True)
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
    """Return latest funding rate snapshots with asset/protocol labels."""
    # Latest funding snapshot per market (single query).
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
    query = query.limit(limit)
    result = await db.execute(query)
    snapshots = result.scalars().all()

    if not snapshots:
        return []

    # Single batched query for all markets + their protocols (avoids N+1).
    market_ids = {s.market_id for s in snapshots}
    mp_rows = await db.execute(
        select(Market, Protocol).where(
            Market.id.in_(market_ids), Market.protocol_id == Protocol.id
        )
    )
    labels: dict[str, tuple[str, str]] = {}
    for m, p in mp_rows.all():
        labels[m.id] = (m.asset, p.name)

    out: list[FundingSnapshotOut] = []
    for snap in snapshots:
        info = labels.get(snap.market_id)
        if info is None:
            continue
        asset_name, protocol_name = info
        # Apply filters in-memory (cheaper than a per-filter subquery join).
        if asset and asset.lower() not in asset_name.lower():
            continue
        if protocol and protocol.lower() not in protocol_name.lower():
            continue
        out.append(
            FundingSnapshotOut(
                id=snap.id,
                market_id=snap.market_id,
                observed_at=snap.observed_at,
                asset=asset_name,
                protocol=protocol_name,
                funding_rate=snap.funding_rate,
                funding_interval_hours=snap.funding_interval_hours,
                annualized_funding=snap.annualized_funding,
                open_interest=snap.open_interest,
                volume_24h=snap.volume_24h,
                long_short_ratio=snap.long_short_ratio,
                mark_price=snap.mark_price,
                index_price=snap.index_price,
            )
        )
    return out


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
) -> list[OpportunityOut]:
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
    result = await db.execute(query)
    snapshots = result.scalars().all()

    if not snapshots:
        return []

    # Single batched query for all markets + protocols (avoids N+1).
    market_ids = {s.market_id for s in snapshots}
    mp_rows = await db.execute(
        select(Market, Protocol).where(
            Market.id.in_(market_ids), Market.protocol_id == Protocol.id
        )
    )
    markets: dict[str, Market] = {}
    protocols: dict[str, Protocol] = {}
    for m, p in mp_rows.all():
        markets[m.id] = m
        protocols[m.id] = p

    # Single batched volatility query for all markets in this set.
    vol_map = await _volatility_map(db, market_ids)

    # Batch-load existing loop calculations instead of one query per snapshot.
    snap_ids = [s.id for s in snapshots]
    calc_rows = await db.execute(
        select(LoopCalculation).where(
            LoopCalculation.lending_snapshot_id.in_(snap_ids),
            LoopCalculation.calc_version == "loop-v1",
        )
    )
    calcs_by_snap: dict[str, LoopCalculation] = {
        c.lending_snapshot_id: c for c in calc_rows.scalars().all()
    }

    loop_opps: list[dict] = []
    weights = _parse_ranker_weights()

    for snap in snapshots:
        market = markets.get(snap.market_id)
        protocol = protocols.get(snap.market_id)
        if market is None or protocol is None:
            continue

        # Apply filters
        if asset_filter and asset_filter.lower() not in market.asset.lower():
            continue
        if protocol_filter and protocol_filter.lower() not in protocol.name.lower():
            continue

        # Economic-edge filter: skip loops whose nominal spread (deposit − borrow)
        # is below the configured floor. A negative nominal spread means the only
        # thing producing positive effective_yield is leverage amplifying an
        # inverted rate — mathematically profitable but with no margin for rate
        # drift, gas, or fees. Default 0.0 = require non-inverted rates; raise to
        # demand a real pre-leverage edge.
        nominal_spread = (snap.deposit_apy or 0.0) - (snap.borrow_apy or 0.0)
        if nominal_spread < settings.DEFI_LOOP_MIN_NOMINAL_SPREAD:
            continue

        max_ltv, liq_threshold = ltv_params_from_snapshot(snap)
        calc_row = calcs_by_snap.get(snap.id)

        if calc_row is None:
            calc = simulate_looping(
                deposit_apy=snap.deposit_apy or 0.0,
                borrow_apy=snap.borrow_apy or 0.0,
                max_ltv=max_ltv,
                liquidation_threshold=liq_threshold,
                initial_capital=10000.0,
                target_ltv=0.7,
                safety_buffer=0.95,
                max_loops=20,
            )
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
            calcs_by_snap[snap.id] = calc_row
        else:
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

        vol_penalty = vol_map.get(snap.market_id, 0.0)

        opp = {
            "yield_score": calc.get("effective_yield", 0.0),
            "liquidity_score": snap.available_liquidity or 0.0,
            "tvl_score": snap.tvl or 0.0,
            "stability_score": snap.deposit_apy or 0.0,
            "utilization_penalty": snap.utilization or 0.0,
            "volatility_penalty": vol_penalty,
            "protocol_risk": protocol.risk_score,
            "_protocol": protocol.name,
            "_asset": market.asset,
            "_calc": calc,
            "_snap": snap,
        }
        loop_opps.append(opp)

    if not loop_opps:
        return []

    ranked = score_opportunities(loop_opps, weights)

    # Attach real confidence signals to each ranked opp.
    # ponytail: sequential, not asyncio.gather — a shared AsyncSession can't run
    # two queries concurrently. Use distinct sessions if this ever needs overlap.
    history_map = await get_yield_history(db, market_ids, "lending_snapshots", "deposit_apy")
    percentile_map = await get_percentile(db, market_ids, "lending_snapshots", "deposit_apy")
    rank_map = await get_historical_rank(db, market_ids, "lending_snapshots", "deposit_apy")
    # Real persistence/depth: snapshot count + distinct observation days (last 30d).
    depth_map = await _history_depth_map(db, market_ids, "lending_snapshots")

    # Deposit APY volatility for Sharpe computation (batched).
    deposit_vol_map = await _volatility_map(db, market_ids, source="lending")

    for r in ranked:
        snap = r["_snap"]
        mid = snap.market_id
        prot = protocols.get(mid)
        cnt, days = depth_map.get(mid, (0, 0))
        r["_history_points"] = cnt
        r["_persistence_days"] = days
        r["_protocol_age_days"] = _age_days(getattr(prot, "deployed_at", None))
        r["_audit_count"] = getattr(prot, "audit_count", 0) or 0

    rate_opportunities(ranked)

    filtered = [
        r
        for r in ranked
        if r.get("_calc", {}).get("effective_yield", 0.0) >= min_yield
        and (r.get("_snap") and (r["_snap"].available_liquidity or 0.0) >= min_liquidity)
    ]

    out: list[OpportunityOut] = []
    for r in filtered:
        calc = r["_calc"]
        snap = r["_snap"]
        mid = snap.market_id
        hist = history_map.get(mid)
        dep_vol = deposit_vol_map.get(mid, 0.0)
        eff_yield = calc.get("effective_yield") or 0.0
        sharpe = (eff_yield / dep_vol) if dep_vol else None
        out.append(
            OpportunityOut(
                strategy_type="loop",
                protocol=r["_protocol"],
                asset=r["_asset"],
                market_id=mid,
                net_apy=calc.get("effective_yield"),
                risk_score=calc.get("risk_score"),
                score=r["score"],
                rank=r["rank"],
                breakdown=r.get("breakdown"),
                weights=r.get("weights"),
                rating=r.get("rating"),
                rating_label=r.get("rating_label"),
                confidence=r.get("confidence"),
                medal=r.get("medal"),
                sharpe=sharpe,
                history=YieldHistoryOut(**hist) if hist else None,
                percentile_90d=percentile_map.get(mid),
                historical_rank=rank_map.get(mid),
                strategy_details={
                    "deposit_apy": snap.deposit_apy,
                    "borrow_apy": snap.borrow_apy,
                    "effective_yield": calc.get("effective_yield"),
                    "leverage": calc.get("leverage"),
                    "safety_margin": calc.get("safety_margin"),
                    "liquidation_distance": calc.get("liquidation_distance"),
                },
            )
        )
    return out


async def _fetch_carry_opportunities(
    db: AsyncSession,
    asset_filter: str,
    protocol_filter: str,
    min_yield: float,
) -> list[OpportunityOut]:
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

    if not snapshots:
        return []

    # Single batched query for funding markets + protocols.
    market_ids = {s.market_id for s in snapshots}
    mp_rows = await db.execute(
        select(Market, Protocol).where(
            Market.id.in_(market_ids), Market.protocol_id == Protocol.id
        )
    )
    markets: dict[str, Market] = {}
    protocols: dict[str, Protocol] = {}
    for m, p in mp_rows.all():
        markets[m.id] = m
        protocols[m.id] = p

    # Build an asset -> (borrow_cost, spot_yield) map ONCE from the latest
    # lending snapshot of every lending market. Avoids re-querying all lending
    # snapshots inside the funding loop (the previous N+1 worst-case).
    lend_by_asset = await _latest_lending_by_asset(db)

    # Batch-load existing carry calculations.
    snap_ids = [s.id for s in snapshots]
    calc_rows = await db.execute(
        select(CarryCalculation).where(
            CarryCalculation.funding_snapshot_id.in_(snap_ids),
            CarryCalculation.calc_version == "carry-v1",
        )
    )
    calcs_by_snap: dict[str, CarryCalculation] = {
        c.funding_snapshot_id: c for c in calc_rows.scalars().all()
    }

    # Batched volatility for all funding markets.
    vol_map = await _volatility_map(db, market_ids)

    carry_opps: list[dict] = []
    weights = _parse_ranker_weights()

    for snap in snapshots:
        market = markets.get(snap.market_id)
        protocol = protocols.get(snap.market_id)
        if market is None or protocol is None:
            continue

        if asset_filter and asset_filter.lower() not in market.asset.lower():
            continue
        if protocol_filter and protocol_filter.lower() not in protocol.name.lower():
            continue

        # A carry trade needs a real borrow leg. If no lending market exists for
        # this asset, borrow_cost/spot_yield are unknown — the opp isn't real,
        # so skip it rather than silently modeling a 0% borrow (which would
        # overstate net_carry vs. opps with a priced borrow leg).
        if market.asset not in lend_by_asset:
            continue
        borrow_cost, spot_yield = lend_by_asset[market.asset]

        calc_row = calcs_by_snap.get(snap.id)
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
            calcs_by_snap[snap.id] = calc_row
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

        vol_penalty = vol_map.get(snap.market_id, 0.0)

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
            "_market_id": snap.market_id,
            "_calc": calc,
        }
        carry_opps.append(opp)

    if not carry_opps:
        return []

    ranked = score_opportunities(carry_opps, weights)

    # Fetch annualized_funding history for carry markets (batched).
    history_map = await get_yield_history(
        db, market_ids, "funding_snapshots", "annualized_funding"
    )
    percentile_map = await get_percentile(db, market_ids, "funding_snapshots", "annualized_funding")
    rank_map = await get_historical_rank(db, market_ids, "funding_snapshots", "annualized_funding")
    # Real persistence/depth for carry markets (last 30d of funding snapshots).
    depth_map = await _history_depth_map(db, market_ids, "funding_snapshots")

    for r in ranked:
        # _snap is not stored on carry opps — use market_id from the funding snap directly
        mid = r.get("_market_id", "")
        prot = protocols.get(mid)
        cnt, days = depth_map.get(mid, (0, 0))
        r["_history_points"] = cnt
        r["_persistence_days"] = days
        r["_protocol_age_days"] = _age_days(getattr(prot, "deployed_at", None))
        r["_audit_count"] = getattr(prot, "audit_count", 0) or 0

    rate_opportunities(ranked)

    filtered = [
        r
        for r in ranked
        if r.get("_calc", {}).get("net_carry", 0.0) >= min_yield
    ]

    out: list[OpportunityOut] = []
    for r in filtered:
        calc = r["_calc"]
        mid = r.get("_market_id", "")
        hist = history_map.get(mid)
        funding_vol = vol_map.get(mid, 0.0)
        net_carry = calc.get("net_carry") or 0.0
        sharpe = (net_carry / funding_vol) if funding_vol else None
        out.append(
            OpportunityOut(
                strategy_type="carry",
                protocol=r["_protocol"],
                asset=r["_asset"],
                market_id=mid or None,
                net_apy=calc.get("net_carry"),
                risk_score=calc.get("risk_score"),
                score=r["score"],
                rank=r["rank"],
                breakdown=r.get("breakdown"),
                weights=r.get("weights"),
                rating=r.get("rating"),
                rating_label=r.get("rating_label"),
                confidence=r.get("confidence"),
                medal=r.get("medal"),
                sharpe=sharpe,
                history=YieldHistoryOut(**hist) if hist else None,
                percentile_90d=percentile_map.get(mid),
                historical_rank=rank_map.get(mid),
                strategy_details={
                    "funding_yield": calc.get("funding_yield"),
                    "spot_yield": calc.get("spot_yield"),
                    "borrow_cost": calc.get("borrow_cost"),
                    "trading_fees": calc.get("trading_fees"),
                    "net_carry": calc.get("net_carry"),
                },
            )
        )
    return out


async def _fetch_market_type_opportunities(
    db: AsyncSession,
    market_type: str,
    asset_filter: str,
    protocol_filter: str,
    min_yield: float,
) -> list[OpportunityOut]:
    """Return opportunities for deposit-only market types (staking, restaking, pendle, stable_lending).

    These market types have no borrow leg; their snapshots are stored in lending_snapshots
    with a matching market_type value. Returns OpportunityOut with strategy_type matching
    the market_type.

    ponytail: currently returns empty — adapters are stubs (NotImplementedError).
    When collectors are wired in, this query will find their snapshots.
    """
    max_ts = func.max(LendingSnapshot.observed_at).label("max_ts")
    sub = (
        select(LendingSnapshot.market_id, max_ts)
        .join(Market, LendingSnapshot.market_id == Market.id)
        .where(Market.market_type == market_type)
        .group_by(LendingSnapshot.market_id)
        .subquery()
    )
    query = (
        select(LendingSnapshot)
        .join(sub, LendingSnapshot.market_id == sub.c.market_id)
        .where(LendingSnapshot.observed_at == sub.c.max_ts)
    )
    result = await db.execute(query)
    snapshots = result.scalars().all()

    if not snapshots:
        return []

    market_ids = {s.market_id for s in snapshots}
    mp_rows = await db.execute(
        select(Market, Protocol).where(
            Market.id.in_(market_ids), Market.protocol_id == Protocol.id
        )
    )
    markets: dict[str, Market] = {}
    protocols: dict[str, Protocol] = {}
    for m, p in mp_rows.all():
        markets[m.id] = m
        protocols[m.id] = p

    # Strategy-type → penalty key mapping.
    # ponytail: only inject the penalty relevant to each type; 0.0 = not applicable.
    _PENALTY_KEY: dict[str, str] = {
        "staking": "slashing_penalty",
        "restaking": "slashing_penalty",
        "pendle": "maturity_penalty",
        "stable_lending": "",  # no strategy-specific penalty
    }

    raw_opps: list[dict] = []
    weights = _parse_ranker_weights()

    for snap in snapshots:
        mkt = markets.get(snap.market_id)
        proto = protocols.get(snap.market_id)
        if mkt is None or proto is None:
            continue
        if asset_filter and asset_filter.lower() not in mkt.asset.lower():
            continue
        if protocol_filter and protocol_filter.lower() not in proto.name.lower():
            continue
        dep_apy = snap.deposit_apy or 0.0
        if dep_apy < min_yield:
            continue

        opp: dict = {
            "yield_score": dep_apy,
            "liquidity_score": snap.available_liquidity or 0.0,
            "tvl_score": snap.tvl or 0.0,
            "stability_score": dep_apy,
            "utilization_penalty": snap.utilization or 0.0,
            "volatility_penalty": 0.0,
            "protocol_risk": proto.risk_score,
            "_protocol": proto.name,
            "_asset": mkt.asset,
            "_market_id": snap.market_id,
            "_dep_apy": dep_apy,
        }

        # Inject strategy-specific penalty (default 0.0 when not applicable).
        pen_key = _PENALTY_KEY.get(market_type, "")
        if pen_key and pen_key in weights:
            opp[pen_key] = 0.0  # placeholder: no collectors yet, so no real value

        raw_opps.append(opp)

    if not raw_opps:
        return []

    ranked = score_opportunities(raw_opps, weights)

    out: list[OpportunityOut] = []
    for r in ranked:
        out.append(
            OpportunityOut(
                strategy_type=market_type,
                protocol=r["_protocol"],
                asset=r["_asset"],
                market_id=r["_market_id"],
                net_apy=r["_dep_apy"],
                risk_score=r.get("protocol_risk"),
                score=r["score"],
                rank=r["rank"],
                breakdown=r.get("breakdown"),
                weights=r.get("weights"),
                strategy_details={
                    "deposit_apy": r["_dep_apy"],
                    "market_type": market_type,
                },
            )
        )
    return out


async def _fetch_cross_protocol_opportunities(
    db: AsyncSession,
    asset_filter: str,
    protocol_filter: str,
    min_yield: float,
) -> list[OpportunityOut]:
    """Return cross-protocol opportunities from persisted CrossProtocolCalculation rows.

    Pairs: deposit on protocol A, borrow same asset on protocol B.
    Falls back to on-the-fly calculation when no persisted rows exist.
    """
    # Load latest lending snapshot per market for deposit-side data.
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
    result = await db.execute(query)
    snapshots = result.scalars().all()

    if not snapshots:
        return []

    market_ids = {s.market_id for s in snapshots}
    mp_rows = await db.execute(
        select(Market, Protocol).where(
            Market.id.in_(market_ids), Market.protocol_id == Protocol.id
        )
    )
    markets: dict[str, Market] = {}
    protocols: dict[str, Protocol] = {}
    for m, p in mp_rows.all():
        markets[m.id] = m
        protocols[m.id] = p

    # Build lookup: asset → list of (market_id, snapshot) for pairing.
    by_asset: dict[str, list[tuple[str, LendingSnapshot]]] = {}
    for snap in snapshots:
        mkt = markets.get(snap.market_id)
        if mkt is None:
            continue
        by_asset.setdefault(mkt.asset, []).append((snap.market_id, snap))

    out: list[OpportunityOut] = []
    rank = 1

    for asset_sym, pairs in by_asset.items():
        if len(pairs) < 2:
            continue  # need at least 2 protocols for a cross-protocol pair

        # For each deposit market, find best borrow market (same asset, different protocol).
        for i, (dep_mid, dep_snap) in enumerate(pairs):
            dep_market = markets.get(dep_mid)
            dep_proto = protocols.get(dep_mid)
            if dep_market is None or dep_proto is None:
                continue
            if asset_filter and asset_filter.lower() not in dep_market.asset.lower():
                continue
            if protocol_filter and protocol_filter.lower() not in dep_proto.name.lower():
                continue

            best_spread = -1e9
            best_borrow: tuple[str, LendingSnapshot] | None = None

            for j, (bor_mid, bor_snap) in enumerate(pairs):
                if bor_mid == dep_mid:
                    continue
                spread = (dep_snap.deposit_apy or 0.0) - (bor_snap.borrow_apy or 0.0)
                if spread > best_spread:
                    best_spread = spread
                    best_borrow = (bor_mid, bor_snap)

            if best_borrow is None or best_spread < min_yield:
                continue

            bor_mid, bor_snap = best_borrow
            bor_proto = protocols.get(bor_mid)

            max_ltv, liq_threshold = ltv_params_from_snapshot(dep_snap)
            calc = calculate_cross_protocol_spread(
                deposit_apy=dep_snap.deposit_apy or 0.0,
                borrow_apy=bor_snap.borrow_apy or 0.0,
                max_ltv=max_ltv,
                liq_threshold=liq_threshold,
            )

            # cross_protocol_penalty: average protocol risk across both legs.
            cross_penalty = (
                (dep_proto.risk_score or 0.0) + (bor_proto.risk_score if bor_proto else 0.0)
            ) / 2.0

            out.append(
                OpportunityOut(
                    strategy_type="cross_protocol",
                    protocol=dep_proto.name,
                    asset=asset_sym,
                    market_id=dep_mid,
                    net_apy=calc["net_spread"],
                    risk_score=calc["risk_score"],
                    score=max(0.0, calc["net_spread"] * 10.0),  # simple scoring
                    rank=rank,
                    breakdown={"cross_protocol_penalty": cross_penalty},
                    strategy_details={
                        "deposit_protocol": dep_proto.name,
                        "deposit_asset": asset_sym,
                        "borrow_protocol": bor_proto.name if bor_proto else "unknown",
                        "borrow_asset": asset_sym,
                        "net_spread": calc["net_spread"],
                        "leverage": calc["leverage"],
                        "safety_margin": calc["safety_margin"],
                        "cross_protocol_penalty": cross_penalty,
                    },
                )
            )
            rank += 1

    return out


async def _latest_lending_by_asset(db: AsyncSession) -> dict[str, tuple[float, float]]:
    """Return {asset: (borrow_apy, deposit_apy)} from the latest lending snapshot per market."""
    max_ts_l = func.max(LendingSnapshot.observed_at).label("max_ts")
    lend_sub = (
        select(LendingSnapshot.market_id, max_ts_l)
        .group_by(LendingSnapshot.market_id)
        .subquery()
    )
    lend_rows = await db.execute(
        select(LendingSnapshot, Market.asset).join(
            lend_sub, LendingSnapshot.market_id == lend_sub.c.market_id
        ).where(LendingSnapshot.observed_at == lend_sub.c.max_ts).join(
            Market, LendingSnapshot.market_id == Market.id
        )
    )
    out: dict[str, tuple[float, float]] = {}
    for snap, asset in lend_rows.all():
        out[asset] = (snap.borrow_apy or 0.0, snap.deposit_apy or 0.0)
    return out


def _age_days(deployed_at: object | None) -> float | None:
    """Protocol deployment age in days, or None when unknown.

    getattr-safe: protocol rows from older fixtures may lack the column.
    """
    if deployed_at is None:
        return None
    try:
        return (datetime.now(UTC) - deployed_at).total_seconds() / 86400.0  # type: ignore[arg-type]
    except TypeError:
        return None


# Trusted snapshot table names for the depth query — literal arg, never user input.
_DEPTH_TABLES = {"lending_snapshots", "funding_snapshots"}


async def _history_depth_map(
    db: AsyncSession, market_ids: set[str], table: str
) -> dict[str, tuple[int, int]]:
    """Real confidence depth inputs per market: (snapshot_count, distinct_days) over last 30d.

    `history_points` (count) drives the depth factor; `persistence_days`
    (distinct calendar days) drives the persistence stub. Distinct from the
    volatility STDDEV query — this measures spread over time, not variance.
    """
    if not market_ids or table not in _DEPTH_TABLES:
        return {}
    sql = text(f"""
        SELECT market_id,
               COUNT(*)                                            AS cnt,
               COUNT(DISTINCT (observed_at AT TIME ZONE 'UTC')::date) AS days
        FROM {table}
        WHERE market_id = ANY(:market_ids)
          AND observed_at >= NOW() - INTERVAL '30 days'
        GROUP BY market_id
    """)
    result = await db.execute(sql, {"market_ids": list(market_ids)})
    out: dict[str, tuple[int, int]] = {}
    for mid, cnt, days in result.all():
        out[mid] = (int(cnt or 0), int(days or 0))
    return out


# Trusted (table, column) pairs for volatility queries — keyed by a literal source
# arg, never user input, so interpolating them into SQL is safe.
_VOLATILITY_SOURCES = {
    "funding": ("funding_snapshots", "funding_rate"),
    "lending": ("lending_snapshots", "deposit_apy"),
}


async def _volatility_map(
    db: AsyncSession, market_ids: set[str], source: str = "funding"
) -> dict[str, float]:
    """Batched volatility (STDDEV of the last N values) for many markets at once.

    `source` selects the snapshot table/column: "funding" (funding_rate) for carry,
    "lending" (deposit_apy) for loop Sharpe.
    """
    if not market_ids:
        return {}
    table, field = _VOLATILITY_SOURCES[source]
    window = settings.DEFI_VOLATILITY_WINDOW
    # DistinctON-style: latest N rows per market, then stddev per market.
    sql = text(f"""
        SELECT market_id, STDDEV({field}) AS vol
        FROM (
            SELECT market_id, {field},
                   ROW_NUMBER() OVER (PARTITION BY market_id
                                      ORDER BY observed_at DESC) AS rn
            FROM {table}
            WHERE market_id = ANY(:market_ids)
        ) AS recent
        WHERE rn <= :window
        GROUP BY market_id
    """)
    result = await db.execute(
        sql, {"market_ids": list(market_ids), "window": window}
    )
    out: dict[str, float] = {}
    for mid, vol in result.all():
        out[mid] = float(vol) if vol is not None else 0.0
    return out


async def _volatility_penalty(db: AsyncSession, market_id: str) -> float:
    """Compute volatility penalty via windowed STDDEV of funding_rate (single market)."""
    return (await _volatility_map(db, {market_id})).get(market_id, 0.0)
