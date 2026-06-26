"""Alert engine — evaluates threshold rules against latest DB data and fires alerts."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Alert,
    CarryCalculation,
    FundingSnapshot,
    LendingSnapshot,
    LoopCalculation,
    Market,
)

logger = logging.getLogger("defi_scanner")


class AlertEngine:
    """Evaluates alert thresholds against latest snapshots/calculations.

    Queries the latest data per market, checks each configured threshold,
    deduplicates (no re-fire within cooldown), persists Alert rows, and
    dispatches notifications to all configured channels.
    """

    def __init__(
        self,
        session_factory: Any,  # async_sessionmaker[AsyncSession] — Any to ease mocking
        channels: dict[str, Any],  # str → NotificationChannel
        thresholds: dict[str, float],
        cooldown_minutes: int = 60,
    ) -> None:
        self._session_factory = session_factory
        self._channels = channels
        self._thresholds = thresholds
        self._cooldown = timedelta(minutes=cooldown_minutes)

    async def evaluate(self) -> list[Alert]:
        """Run one evaluation cycle. Returns list of newly fired alerts."""
        fired: list[Alert] = []
        async with self._session_factory() as session:
            result = await session.execute(select(Market))
            markets = result.scalars().all()

            for market in markets:
                # ── fetch latest data for this market ──────────────────────
                lend_snap = await self._latest_lending(session, market.id)
                fund_snap = await self._latest_funding(session, market.id)
                loop_calc = await self._latest_loop(session, market.id)
                carry_calc = await self._latest_carry(session, market.id)

                # ponytail: one explicit checks list beats a config loop
                checks: list[tuple[str, float, float | None, str, bool]] = [
                    (
                        "borrow_apy_lt",
                        self._thresholds.get("borrow_apy", 3.0),
                        lend_snap.borrow_apy if lend_snap else None,
                        "borrow_apy",
                        True,  # lower-is-better
                    ),
                    (
                        "funding_rate_gt",
                        self._thresholds.get("funding_rate", 20.0),
                        fund_snap.annualized_funding if fund_snap else None,
                        "annualized_funding",
                        False,  # higher-is-better
                    ),
                    (
                        "loop_yield_gt",
                        self._thresholds.get("loop_yield", 10.0),
                        loop_calc.effective_yield if loop_calc else None,
                        "effective_yield",
                        False,
                    ),
                    (
                        "net_carry_gt",
                        self._thresholds.get("net_carry", 12.0),
                        carry_calc.net_carry if carry_calc else None,
                        "net_carry",
                        False,
                    ),
                ]

                for alert_type, threshold, value, metric_name, is_lower in checks:
                    if value is None:
                        continue
                    breached = value < threshold if is_lower else value > threshold
                    if not breached:
                        continue

                    # Dedup: skip if same alert_type+market_id fired within cooldown
                    cutoff = datetime.now(UTC) - self._cooldown
                    dedup_q = (
                        select(Alert)
                        .where(
                            Alert.alert_type == alert_type,
                            Alert.market_id == market.id,
                            Alert.fired_at >= cutoff,
                        )
                        .limit(1)
                    )
                    dedup_result = await session.execute(dedup_q)
                    if dedup_result.scalar_one_or_none() is not None:
                        logger.debug(
                            "Skipping %s for %s — already fired within cooldown",
                            alert_type,
                            market.asset,
                        )
                        continue

                    # Fire alert
                    message = (
                        f"🚨 {alert_type} ALERT: {market.asset} "
                        f"{metric_name}={value:.2f}% (threshold={threshold:.1f}%)"
                    )
                    primary_channel = next(iter(self._channels), "log")
                    alert = Alert(
                        alert_type=alert_type,
                        threshold_value=threshold,
                        triggered_value=value,
                        market_id=market.id,
                        channel=primary_channel,
                        status="fired",
                        raw_message=message,
                    )
                    session.add(alert)
                    fired.append(alert)

                    for ch_name, ch in self._channels.items():
                        sent = await ch.send(message)
                        if not sent:
                            logger.warning("Channel %s failed to deliver alert", ch_name)

            if fired:
                await session.commit()
                logger.info("Alert engine fired %d alert(s)", len(fired))

        return fired

    # ── query helpers ─────────────────────────────────────────────────────

    @staticmethod
    async def _latest_lending(session: AsyncSession, market_id: str) -> LendingSnapshot | None:
        q = (
            select(LendingSnapshot)
            .where(LendingSnapshot.market_id == market_id)
            .order_by(LendingSnapshot.observed_at.desc())
            .limit(1)
        )
        r = await session.execute(q)
        return r.scalar_one_or_none()

    @staticmethod
    async def _latest_funding(session: AsyncSession, market_id: str) -> FundingSnapshot | None:
        q = (
            select(FundingSnapshot)
            .where(FundingSnapshot.market_id == market_id)
            .order_by(FundingSnapshot.observed_at.desc())
            .limit(1)
        )
        r = await session.execute(q)
        return r.scalar_one_or_none()

    @staticmethod
    async def _latest_loop(session: AsyncSession, market_id: str) -> LoopCalculation | None:
        q = (
            select(LoopCalculation)
            .join(LendingSnapshot, LoopCalculation.lending_snapshot_id == LendingSnapshot.id)
            .where(LendingSnapshot.market_id == market_id)
            .order_by(LoopCalculation.created_at.desc())
            .limit(1)
        )
        r = await session.execute(q)
        return r.scalar_one_or_none()

    @staticmethod
    async def _latest_carry(session: AsyncSession, market_id: str) -> CarryCalculation | None:
        q = (
            select(CarryCalculation)
            .join(FundingSnapshot, CarryCalculation.funding_snapshot_id == FundingSnapshot.id)
            .where(FundingSnapshot.market_id == market_id)
            .order_by(CarryCalculation.created_at.desc())
            .limit(1)
        )
        r = await session.execute(q)
        return r.scalar_one_or_none()
