"""Protocol metadata collectors — real external signals for confidence completeness.

Two collectors in one module, replacing the former static PROTOCOL_METADATA
heuristic in rating.py:

  ProtocolAuditCollector — pulls audit presence (+ contract address/chain) from
    DefiLlama's public /protocols list (free, no API key). Persists
    audit_count / audit_source / address / metadata_updated_at onto the
    Protocol row.

  ProtocolAgeCollector — for protocols whose on-chain contract address is known
    on an EVM chain with a configured RPC, resolves the deployment block's
    timestamp via a get_code binary search and persists deployed_at. Skips
    non-EVM chains (e.g. Hyperliquid) honestly — those remain age-unknown.

Confidence (rating.py) reads these real fields instead of static booleans.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.calculations.rating import _protocol_slug
from app.config import settings
from app.models import Protocol

logger = logging.getLogger("defi_scanner")

# Chains we can resolve on-chain deployment for. Only Ethereum mainnet RPC is
# configured by default; extend the map (or wire a settings-driven dict) to age
# other EVM chains. Non-EVM protocols stay age-unknown — that's honest, not a
# silent stub.
# ponytail: single-chain map; add an entry per chain when its RPC is configured.
_CHAIN_RPCS: dict[str, str] = {"ethereum": settings.RPC_URL}

# ── shared helpers ────────────────────────────────────────────────────────────


def _has_audit(entry: dict) -> bool:
    """DefiLlama exposes audit info inconsistently across endpoints/release —
    accept truthy presence in any of the known fields rather than pinning one."""
    for key in ("audit", "audits", "audit_ids", "audit_links", "audit_count"):
        val = entry.get(key)
        if val:
            return True
    return False


# ── ProtocolAuditCollector ────────────────────────────────────────────────────


class ProtocolAuditCollector:
    """Persist real audit presence + contract address from DefiLlama onto Protocol rows."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        client: httpx.AsyncClient | None = None,
        url: str | None = None,
    ) -> None:
        self._sf = session_factory
        self._client = client
        self._owns_client = client is None
        self._url = url or settings.DEFI_LLAMA_PROTOCOLS_URL

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def collect(self) -> None:
        """One cycle: fetch DefiLlama /protocols, match by slug, upsert metadata."""
        try:
            client = await self._get_client()
            resp = await client.get(self._url)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            logger.exception("ProtocolAuditCollector: fetch failed")
            return

        if not isinstance(data, list):
            logger.error("DefiLlama /protocols unexpected shape: %s", type(data).__name__)
            return

        # Index by slug (lowercased) for O(1) lookup by our protocol slug.
        by_slug: dict[str, dict] = {}
        for e in data:
            if not isinstance(e, dict):
                continue
            slug = str(e.get("slug") or "").lower()
            if slug:
                by_slug.setdefault(slug, e)

        async with self._sf() as session:
            rows = (await session.execute(select(Protocol))).scalars().all()
            if not rows:
                return
            now = datetime.now(UTC)
            changed = 0
            for p in rows:
                entry = by_slug.get(_protocol_slug(p.name))
                if entry is None:
                    continue
                p.audit_count = 1 if _has_audit(entry) else 0
                p.audit_source = "defillama"
                address = entry.get("address")
                if address and not p.address:
                    # Keep first-seen address; don't overwrite a configured value.
                    p.address = str(address)
                p.metadata_updated_at = now
                changed += 1
            if changed:
                await session.commit()
                logger.info("ProtocolAuditCollector: updated %d protocol(s)", changed)


# ── ProtocolAgeCollector ──────────────────────────────────────────────────────


class ProtocolAgeCollector:
    """Resolve real on-chain deployment timestamps for EVM protocols via get_code binary search."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        chain_rpcs: dict[str, str] | None = None,
    ) -> None:
        self._sf = session_factory
        self._chain_rpcs = chain_rpcs or _CHAIN_RPCS

    async def collect(self) -> None:
        """One cycle: resolve deployed_at for protocols missing it (address + RPC known)."""
        async with self._sf() as session:
            rows = (await session.execute(select(Protocol))).scalars().all()
            if not rows:
                return
            resolved = 0
            for p in rows:
                if p.deployed_at or not p.address:
                    continue  # already known, or nothing to resolve from
                rpc = self._chain_rpcs.get((p.chain or "").lower())
                if not rpc:
                    continue  # no RPC configured for this chain — age stays unknown (honest)
                try:
                    ts = await asyncio.to_thread(self._resolve_deployment_sync, rpc, p.address)
                except Exception:
                    logger.exception(
                        "ProtocolAgeCollector: resolve failed for %s (%s)", p.name, p.address
                    )
                    continue
                if ts is not None:
                    p.deployed_at = ts
                    resolved += 1
            if resolved:
                await session.commit()
                logger.info(
                    "ProtocolAgeCollector: resolved deployment for %d protocol(s)", resolved
                )

    def _resolve_deployment_sync(self, rpc: str, address: str) -> datetime | None:
        """Binary-search the block where `address`'s code first appears, return its timestamp.

        ~log2(head_block) get_code calls (~24 on Ethereum mainnet). Run off the
        event loop via asyncio.to_thread; only re-resolves protocols whose
        deployed_at is still None (cached after the first success).
        """
        from web3 import Web3  # lazy import keeps test-time deps light

        w3 = Web3(Web3.HTTPProvider(rpc))
        checksum = Web3.to_checksum_address(address)
        hi = w3.eth.block_number
        if not bool(w3.eth.get_code(checksum, hi)):
            return None  # not a contract at head (wrong chain / EOA) — skip
        lo = 0
        while lo < hi:
            mid = (lo + hi) // 2
            if bool(w3.eth.get_code(checksum, mid)):
                hi = mid
            else:
                lo = mid + 1
        block = w3.eth.get_block(lo)
        return datetime.fromtimestamp(int(block["timestamp"]), tz=UTC)
