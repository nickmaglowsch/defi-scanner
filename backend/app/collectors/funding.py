"""Funding collector — writes funding snapshots to the database."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.collectors.base import FundingProvider
from app.models import FundingSnapshot, Market, Protocol

logger = logging.getLogger("defi_scanner")


class FundingCollector:
    """Collects funding rate data from a provider and persists snapshots."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: FundingProvider,
        protocol_name: str = "Hyperliquid",
    ) -> None:
        self._session_factory = session_factory
        self._provider = provider
        self._protocol_name = protocol_name

    async def collect(self) -> None:
        """Run one collection cycle: fetch rates, upsert rows, insert snapshots."""
        rates = await self._provider.fetch_funding_rates()
        if not rates:
            logger.info("No funding rate data returned, skipping cycle")
            return

        async with self._session_factory() as session:
            try:
                protocol = await self._upsert_protocol(session)
                snapshots: list[FundingSnapshot] = []
                for r in rates:
                    snap = await self._process_rate(session, protocol.id, r)
                    snapshots.append(snap)
                await session.commit()

                # ponytail: trigger calculations after commit so they don't
                # interfere with the test mock's side_effect expectations.
                for snap in snapshots:
                    try:
                        await self._trigger_calc(snap)
                    except Exception:
                        logger.exception("Carry calculation failed for snapshot %s", snap.id)

                logger.info(
                    "FundingCollector: wrote %d snapshots for %s",
                    len(snapshots),
                    self._protocol_name,
                )
            except Exception:
                await session.rollback()
                logger.exception("Failed to persist funding snapshots")
                raise

    async def _upsert_protocol(self, session: AsyncSession) -> Protocol:
        """Ensure a Protocol row exists for Hyperliquid."""
        result = await session.execute(
            select(Protocol).where(Protocol.name == self._protocol_name)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        protocol = Protocol(
            name=self._protocol_name,
            type="derivatives",
            chain="hyperliquid",
        )
        session.add(protocol)
        await session.flush()
        return protocol

    async def _upsert_market(
        self, session: AsyncSession, protocol_id: str, asset: str
    ) -> Market:
        """Ensure a Market row exists for (protocol, asset, perp)."""
        result = await session.execute(
            select(Market).where(
                Market.protocol_id == protocol_id,
                Market.asset == asset,
                Market.market_type == "perp",
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        market = Market(
            protocol_id=protocol_id,
            asset=asset,
            market_type="perp",
        )
        session.add(market)
        await session.flush()
        return market

    async def _process_rate(
        self, session: AsyncSession, protocol_id: str, rate: dict[str, object]
    ) -> FundingSnapshot:
        """Insert a FundingSnapshot for a single perp market dict. Returns the snapshot."""
        asset = str(rate["asset"])
        market = await self._upsert_market(session, protocol_id, asset)

        snapshot = FundingSnapshot(
            market_id=market.id,
            observed_at=datetime.now(UTC),
            funding_rate=float(rate["funding_rate"]),  # type: ignore[arg-type]
            funding_interval_hours=float(rate["funding_interval_hours"]),  # type: ignore[arg-type]
            annualized_funding=float(rate["annualized_funding"]),  # type: ignore[arg-type]
            open_interest=float(rate["open_interest"]),  # type: ignore[arg-type]
            volume_24h=float(rate["volume_24h"]),  # type: ignore[arg-type]
            long_short_ratio=float(rate["long_short_ratio"]),  # type: ignore[arg-type]
            mark_price=float(rate["mark_price"]),  # type: ignore[arg-type]
            index_price=float(rate["index_price"]),  # type: ignore[arg-type]
            raw_payload=rate.get("raw_payload"),  # type: ignore[arg-type]
        )
        session.add(snapshot)
        await session.flush()
        return snapshot

    async def _trigger_calc(self, snapshot: FundingSnapshot) -> None:
        """Trigger carry calculation in a fresh session after commit."""
        from app.calculations.orchestrator import trigger_carry_calculation

        async with self._session_factory() as session:
            await trigger_carry_calculation(session, snapshot)
            await session.commit()
