"""Collector runner — wires all data collectors into a background task loop.

Registry-driven: every enabled entry in protocols/registry.yaml gets a
collector task. Add new adapters to the slug→factory maps below; no changes
to main.py needed.
"""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.db.session import async_session_factory
from app.protocols.registry import Registry, RegistryEntry, load_registry

logger = logging.getLogger("defi_scanner")

# Global shutdown event — set to stop all collector loops.
_shutdown_event = asyncio.Event()
_tasks: list[asyncio.Task[object]] = []

# ── Slug → adapter factory maps ───────────────────────────────────────────────
# Lazy imports inside each factory keep disabled-entry modules unimported.
# ponytail: stub adapters (GMX, Drift, Vertex, dYdX) raise NotImplementedError
# at fetch time — they log and continue via the _run_loop exception handler.

_RPC_BY_CHAIN: dict[str, str] = {
    "base": settings.RPC_URL,       # overridden by DEFI_RPC_URL_BASE if set
    "arbitrum": settings.RPC_URL,   # overridden by DEFI_RPC_URL_ARBITRUM if set
    "optimism": settings.RPC_URL,   # overridden by DEFI_RPC_URL_OPTIMISM if set
    "polygon": settings.RPC_URL,    # overridden by DEFI_RPC_URL_POLYGON if set
    "ethereum": settings.RPC_URL,
}

# Populate per-chain overrides from env (DEFI_ prefix already stripped by Settings).
# We read them directly from os.environ here because adding every possible chain
# to Settings would pre-require knowing all chains at import time.
import os as _os
for _chain, _env_key in [
    ("base", "DEFI_RPC_URL_BASE"),
    ("arbitrum", "DEFI_RPC_URL_ARBITRUM"),
    ("optimism", "DEFI_RPC_URL_OPTIMISM"),
    ("polygon", "DEFI_RPC_URL_POLYGON"),
]:
    _val = _os.environ.get(_env_key)
    if _val:
        _RPC_BY_CHAIN[_chain] = _val


def _rpc_for(entry: RegistryEntry) -> str:
    return entry.rpc_url or _RPC_BY_CHAIN.get(entry.chain, settings.RPC_URL)


# ── Per-type builder functions (patchable for tests) ─────────────────────────


def _build_lending_collector(entry: RegistryEntry, session_factory: object) -> object:
    """Instantiate the right lending adapter for the registry entry and wrap it."""
    from app.collectors.lending import LendingCollector

    # Slug-based factory: import adapter only when needed.
    if entry.slug == "aave-v3":
        from app.collectors.aave import AaveV3Adapter
        adapter = AaveV3Adapter(registry_entry=entry, rpc_url=_rpc_for(entry))
    elif entry.slug == "morpho":
        from app.collectors.morpho import MorphoAdapter
        adapter = MorphoAdapter(entry=entry)
    elif entry.slug == "spark":
        from app.collectors.spark import SparkAdapter
        adapter = SparkAdapter(entry=entry)
    elif entry.slug == "euler":
        from app.collectors.euler import EulerAdapter
        adapter = EulerAdapter(entry=entry)
    else:
        # Unknown lending slug — log and skip (no task created).
        logger.warning("No lending adapter registered for slug=%r, skipping", entry.slug)
        return None  # type: ignore[return-value]

    return LendingCollector(session_factory, adapter, protocol_name=entry.protocol)  # type: ignore[arg-type]


def _build_funding_collector(entry: RegistryEntry, session_factory: object) -> object:
    """Instantiate the right funding adapter for the registry entry and wrap it."""
    from app.collectors.funding import FundingCollector

    if entry.slug == "hyperliquid":
        from app.collectors.hyperliquid import HyperliquidAdapter
        adapter = HyperliquidAdapter(api_url=entry.pool_address or settings.HYPERLIQUID_API_URL)
    elif entry.slug == "gmx":
        from app.collectors.gmx import GmxAdapter
        adapter = GmxAdapter()
    elif entry.slug == "drift":
        from app.collectors.drift import DriftAdapter
        adapter = DriftAdapter()
    elif entry.slug == "vertex":
        from app.collectors.vertex import VertexAdapter
        adapter = VertexAdapter()
    elif entry.slug == "dydx":
        from app.collectors.dydx import DydxAdapter
        adapter = DydxAdapter(api_url=settings.DYDX_INDEXER_URL)
    else:
        logger.warning("No funding adapter registered for slug=%r, skipping", entry.slug)
        return None  # type: ignore[return-value]

    return FundingCollector(session_factory, adapter, protocol_name=entry.protocol)  # type: ignore[arg-type]


# ── Infrastructure tasks (metadata + alerts) — separated for testability ─────


def _start_infrastructure_tasks() -> None:
    """Create and register metadata + alert-engine tasks into _tasks."""
    from app.collectors.protocol_metadata import ProtocolAgeCollector, ProtocolAuditCollector

    audit = ProtocolAuditCollector(async_session_factory)
    _tasks.append(asyncio.create_task(
        _run_loop(audit.collect, settings.DEFI_PROTOCOL_METADATA_INTERVAL_SECONDS),
        name="protocol-audit-collector",
    ))

    age = ProtocolAgeCollector(async_session_factory)
    _tasks.append(asyncio.create_task(
        _run_loop(age.collect, settings.DEFI_PROTOCOL_METADATA_INTERVAL_SECONDS),
        name="protocol-age-collector",
    ))

    from app.alerts import run_alerts
    _tasks.append(asyncio.create_task(run_alerts(_shutdown_event), name="alert-engine"))


# ── Core loop ─────────────────────────────────────────────────────────────────


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

    Registry-driven: loads protocols/registry.yaml, skips disabled entries,
    creates one task per enabled entry using the slug→builder factory.
    Infrastructure tasks (metadata, alerts) are always created.
    """
    registry: Registry = load_registry()
    interval = settings.COLLECTOR_INTERVAL_SECONDS

    for entry in registry.entries:
        if not entry.enabled:
            logger.debug("Skipping disabled registry entry: %s/%s", entry.slug, entry.chain)
            continue

        collector = None
        if entry.type == "lending":
            collector = _build_lending_collector(entry, async_session_factory)
        elif entry.type == "derivatives":
            collector = _build_funding_collector(entry, async_session_factory)
        # ponytail: staking/restaking/pendle types have no adapter yet — skip silently.

        if collector is not None:
            task_name = f"{entry.type}-collector-{entry.slug}-{entry.chain}"
            _tasks.append(asyncio.create_task(
                _run_loop(collector.collect, interval),
                name=task_name,
            ))

    _start_infrastructure_tasks()

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
    """Signal all collector loops to stop gracefully and cancel tasks."""
    _shutdown_event.set()
    for t in _tasks:
        if not t.done():
            t.cancel()
