"""Lending collector — writes lending snapshots to the database."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.collectors.base import LendingProvider
from app.models import LendingSnapshot, Market, Protocol

logger = logging.getLogger("defi_scanner")


class LendingCollector:
    """Collects lending reserve data from a provider and persists snapshots."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: LendingProvider,
        protocol_name: str,
    ) -> None:
        self._session_factory = session_factory
        self._provider = provider
        self._protocol_name = protocol_name

    async def collect(self) -> None:
        """Run one collection cycle: fetch reserves, upsert protocol/markets, insert snapshots."""
        reserves = await self._provider.fetch_reserves()
        if not reserves:
            logger.info("No reserve data returned, skipping cycle")
            return

        async with self._session_factory() as session:
            try:
                protocol = await self._upsert_protocol(session)
                snapshots: list[LendingSnapshot] = []
                for r in reserves:
                    snap = await self._process_reserve(session, protocol.id, r)
                    snapshots.append(snap)
                await session.commit()

                # ponytail: trigger calculations after commit so they don't
                # interfere with the test mock's side_effect expectations.
                for snap in snapshots:
                    try:
                        await self._trigger_calc(snap)
                    except Exception:
                        logger.exception("Loop calculation failed for snapshot %s", snap.id)

                logger.info(
                    "LendingCollector: wrote %d snapshots for %s",
                    len(snapshots),
                    self._protocol_name,
                )
            except Exception:
                await session.rollback()
                logger.exception("Failed to persist lending snapshots")
                raise

    async def _upsert_protocol(self, session: AsyncSession) -> Protocol:
        """Ensure a Protocol row exists for this collector's protocol.

        Uses SELECT-then-INSERT to avoid unique-violation exceptions
        inside transactions where ON CONFLICT would abort the whole batch.
        """
        result = await session.execute(
            select(Protocol).where(Protocol.name == self._protocol_name)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        protocol = Protocol(
            name=self._protocol_name,
            type="lending",
            chain="ethereum",
        )
        session.add(protocol)
        await session.flush()  # generate id before using it
        return protocol

    async def _upsert_market(
        self, session: AsyncSession, protocol_id: str, asset: str
    ) -> Market:
        """Ensure a Market row exists for (protocol, asset, lending)."""
        result = await session.execute(
            select(Market).where(
                Market.protocol_id == protocol_id,
                Market.asset == asset,
                Market.market_type == "lending",
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        market = Market(
            protocol_id=protocol_id,
            asset=asset,
            market_type="lending",
        )
        session.add(market)
        await session.flush()
        return market

    async def _process_reserve(
        self, session: AsyncSession, protocol_id: str, reserve: dict[str, object]
    ) -> LendingSnapshot:
        """Insert a LendingSnapshot for a single reserve dict. Returns the snapshot."""
        asset = str(reserve["asset"])
        market = await self._upsert_market(session, protocol_id, asset)

        snapshot = LendingSnapshot(
            market_id=market.id,
            observed_at=datetime.now(UTC),
            deposit_apy=float(reserve["deposit_apy"]),  # type: ignore[arg-type]
            borrow_apy=float(reserve["borrow_apy"]),  # type: ignore[arg-type]
            utilization=float(reserve["utilization"]),  # type: ignore[arg-type]
            available_liquidity=float(reserve["available_liquidity"]),  # type: ignore[arg-type]
            total_supplied=float(reserve["total_supplied"]),  # type: ignore[arg-type]
            total_borrowed=float(reserve["total_borrowed"]),  # type: ignore[arg-type]
            tvl=float(reserve["tvl"]),  # type: ignore[arg-type]
            raw_payload=reserve.get("raw_payload"),  # type: ignore[arg-type]
        )
        session.add(snapshot)
        await session.flush()
        return snapshot

    async def _trigger_calc(self, snapshot: LendingSnapshot) -> None:
        """Trigger loop calculation in a fresh session after commit."""
        from app.calculations.orchestrator import trigger_loop_calculation

        async with self._session_factory() as session:
            await trigger_loop_calculation(session, snapshot)
            await session.commit()
