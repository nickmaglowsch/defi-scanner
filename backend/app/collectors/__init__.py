"""Collector runner — wires all data collectors into a background task loop.

Add new collectors here (not in main.py) so task-04 can extend without conflicts.
"""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.db.session import async_session_factory

logger = logging.getLogger("defi_scanner")

# Global shutdown event — set to stop all collector loops.
_shutdown_event = asyncio.Event()
_tasks: list[asyncio.Task[object]] = []


async def _run_loop(collect_fn: object, interval_seconds: int) -> None:
    """Call collect_fn repeatedly, sleeping interval_seconds between cycles."""
    while not _shutdown_event.is_set():
        try:
            await collect_fn()  # type: ignore[call-arg]
        except Exception:
            logger.exception("Collector cycle failed, will retry in %ds", interval_seconds)
        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            pass  # interval elapsed — loop again


async def run_collectors() -> None:
    """Create all data collectors and start their background loops.

    Called from the FastAPI lifespan. Add new collector types here.
    task-04 will add Hyperliquid funding collector by importing and
    scheduling it below — no changes to main.py needed.
    """
    from app.collectors.aave import AaveV3Adapter
    from app.collectors.lending import LendingCollector

    # Parse AAVE_ASSETS env: "SYM:0xAddr,..."
    assets: dict[str, str] = {}
    for chunk in settings.AAVE_ASSETS.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        sym, addr = chunk.split(":", 1)
        assets[sym.strip()] = addr.strip()

    aave = AaveV3Adapter(
        rpc_url=settings.RPC_URL,
        pool_address=settings.AAVE_POOL_ADDRESS,
        assets=assets,
    )
    lending = LendingCollector(async_session_factory, aave, protocol_name="Aave V3")
    task = asyncio.create_task(
        _run_loop(lending.collect, settings.COLLECTOR_INTERVAL_SECONDS),
        name="lending-collector-AaveV3",
    )
    _tasks.append(task)

    # ── Hyperliquid funding collector ────────────────────────────────────────
    from app.collectors.funding import FundingCollector
    from app.collectors.hyperliquid import HyperliquidAdapter

    hyperliquid = HyperliquidAdapter(api_url=settings.HYPERLIQUID_API_URL)
    funding = FundingCollector(async_session_factory, hyperliquid)
    task = asyncio.create_task(
        _run_loop(funding.collect, settings.COLLECTOR_INTERVAL_SECONDS),
        name="funding-collector-Hyperliquid",
    )
    _tasks.append(task)

    # ── Protocol metadata collectors (real confidence signals) ───────────────
    # Audit presence + contract address from DefiLlama; on-chain deployment
    # timestamp via get_code binary search. Refreshed hourly — deploy/audit
    # info changes rarely, so this keeps free-RPC rate limits happy.
    from app.collectors.protocol_metadata import (
        ProtocolAgeCollector,
        ProtocolAuditCollector,
    )

    audit = ProtocolAuditCollector(async_session_factory)
    task = asyncio.create_task(
        _run_loop(audit.collect, settings.DEFI_PROTOCOL_METADATA_INTERVAL_SECONDS),
        name="protocol-audit-collector",
    )
    _tasks.append(task)

    age = ProtocolAgeCollector(async_session_factory)
    task = asyncio.create_task(
        _run_loop(age.collect, settings.DEFI_PROTOCOL_METADATA_INTERVAL_SECONDS),
        name="protocol-age-collector",
    )
    _tasks.append(task)

    # ── Alert engine ──────────────────────────────────────────────────────
    from app.alerts import run_alerts

    task = asyncio.create_task(run_alerts(_shutdown_event), name="alert-engine")
    _tasks.append(task)

    # Wait for shutdown signal, then cancel all tasks.
    logger.info("Collectors + alert engine running; %d task(s) started", len(_tasks))
    await _shutdown_event.wait()
    for t in _tasks:
        if not t.done():
            t.cancel()
    results = await asyncio.gather(*_tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception) and not isinstance(r, asyncio.CancelledError):
            logger.warning("Collector task raised during shutdown: %s", r)


async def shutdown_collectors() -> None:
    """Signal all collector loops to stop gracefully."""
    _shutdown_event.set()
