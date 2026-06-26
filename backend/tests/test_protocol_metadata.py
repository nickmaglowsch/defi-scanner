"""Tests for the protocol metadata collectors (real confidence signals)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.collectors.protocol_metadata import (
    ProtocolAgeCollector,
    ProtocolAuditCollector,
    _has_audit,
)

# ── _has_audit defensive parsing ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "entry,expected",
    [
        ({"audit": "https://audits/aave"}, True),
        ({"audit_ids": ["audit-1"]}, True),
        ({"audits": ["a", "b"]}, True),
        ({"audit_count": 0}, False),
        ({"audit_count": 2}, True),
        ({"audit_links": []}, False),
        ({"audit_links": ["x"]}, True),
        ({}, False),
    ],
)
def test_has_audit_accepts_any_known_field(entry, expected):
    assert _has_audit(entry) is expected


# ── ProtocolAuditCollector ─────────────────────────────────────────────────────
# Each Protocol row is a SimpleNamespace so attribute assignment works like ORM.


def _protocol_row(name="Aave V3", **kw):
    base = dict(
        id="p1",
        name=name,
        type="lending",
        chain="ethereum",
        risk_score=0.5,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        address=None,
        deployed_at=None,
        audit_count=0,
        audit_source=None,
        metadata_updated_at=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _make_session_factory(rows):
    """A mock async-session-factory returning `rows` for select(Protocol)."""

    class _Ctx:
        async def __aenter__(self):
            return self._session

        async def __aexit__(self, exc_type, exc, tb):
            pass

    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()

    factory = MagicMock()
    ctx = _Ctx()
    ctx._session = session
    factory.return_value = ctx
    factory._session = session
    return factory


def _mock_response(payload: object) -> httpx.Response:
    req = httpx.Request("GET", "https://example.test/protocols")
    import json

    return httpx.Response(200, content=json.dumps(payload).encode(), request=req)


@pytest.mark.asyncio
async def test_audit_collector_matches_by_slug_and_persists_presence():
    """Aave V3 -> slug 'aave' -> DefiLlama entry with audits -> audit_count=1 + address set."""
    rows = [_protocol_row("Aave V3")]
    factory = _make_session_factory(rows)

    payload = [
        {"slug": "aave", "address": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
         "audit_ids": ["audit-1"]},
        {"slug": "compound", "address": "0x...", "audit": None},   # no audit
        {"slug": "hyperliquid", "address": None, "audit_ids": []},  # not our row here
    ]
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: _mock_response(payload)))
    collector = ProtocolAuditCollector(factory, client=client)

    await collector.collect()

    p = rows[0]
    assert p.audit_count == 1
    assert p.audit_source == "defillama"
    assert p.address == "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
    assert p.metadata_updated_at is not None
    factory._session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_audit_collector_no_audit_entry_means_zero():
    """Matching slug but no audit info -> audit_count=0 (real 'no audits known')."""
    rows = [_protocol_row("Acme"), _protocol_row("Aave V3")]
    # Only 'acme' has a DefiLlama entry, and it has no audit info.
    factory = _make_session_factory(rows)
    payload = [{"slug": "acme", "address": "0xabc"}]
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: _mock_response(payload)))
    collector = ProtocolAuditCollector(factory, client=client)

    await collector.collect()

    acme = next(r for r in rows if r.name == "Acme")
    assert acme.audit_count == 0
    assert acme.address == "0xabc"
    # Aave has no DefiLlama entry this cycle -> untouched.
    aave = next(r for r in rows if r.name == "Aave V3")
    assert aave.audit_count == 0
    assert aave.metadata_updated_at is None


@pytest.mark.asyncio
async def test_audit_collector_does_not_overwrite_existing_address():
    """A protocol already carrying an address is not re-set by DefiLlama."""
    rows = [_protocol_row("Aave V3", address="0xCONFIGURED")]
    factory = _make_session_factory(rows)
    payload = [{"slug": "aave", "address": "0x87870Bca...DIFFERENT", "audit_ids": ["x"]}]
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: _mock_response(payload)))
    collector = ProtocolAuditCollector(factory, client=client)

    await collector.collect()
    assert rows[0].address == "0xCONFIGURED"


@pytest.mark.asyncio
async def test_audit_collector_skips_fetch_failure_gracefully():
    """HTTP error -> no crash, nothing committed."""
    rows = [_protocol_row("Aave V3")]
    factory = _make_session_factory(rows)
    client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req: httpx.Response(500, request=req)))
    collector = ProtocolAuditCollector(factory, client=client)

    await collector.collect()
    factory._session.commit.assert_not_awaited()
    assert rows[0].metadata_updated_at is None


@pytest.mark.asyncio
async def test_audit_collector_no_protocols_no_commit():
    factory = _make_session_factory([])  # no protocol rows
    payload = [{"slug": "aave", "audit_ids": ["x"]}]
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: _mock_response(payload)))
    collector = ProtocolAuditCollector(factory, client=client)

    await collector.collect()
    factory._session.commit.assert_not_awaited()


# ── ProtocolAgeCollector ───────────────────────────────────────────────────────


def _make_w3(code_from_block: int, timestamp: int, head: int = 10_000):
    """Fake web3 where the address has code at blk >= code_from_block."""
    w3 = MagicMock()
    w3.eth.block_number = head
    w3.eth.get_code = MagicMock(
        side_effect=lambda addr, blk: b"0x6080" if blk >= code_from_block else b""
    )
    w3.eth.get_block = MagicMock(return_value={"timestamp": timestamp})
    return w3


@pytest.fixture
def patch_web3(monkeypatch):
    """Patch sys.modules['web3'] so a given w3 mock is returned from Web3(provider).

    The collector does `from web3 import Web3; Web3(Web3.HTTPProvider(rpc))` plus
    `Web3.to_checksum_address(addr)`. The stub wires all three at module level.
    """

    import sys

    def _install(w3) -> None:
        def _ctor(provider=None):
            return w3

        _ctor.to_checksum_address = lambda a: a
        _ctor.HTTPProvider = lambda url: None

        fake = MagicMock()
        fake.Web3 = _ctor
        monkeypatch.setitem(sys.modules, "web3", fake)

    return _install


@pytest.mark.asyncio
async def test_age_collector_resolves_deployment_via_binary_search(patch_web3):
    """Protocol with address + ethereum chain -> deployed_at set from block timestamp."""
    block_ts = 1_700_000_000
    rows = [_protocol_row("Aave V3", address="0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
                          chain="ethereum")]
    factory = _make_session_factory(rows)
    patch_web3(_make_w3(code_from_block=1_500, timestamp=block_ts))

    collector = ProtocolAgeCollector(factory, chain_rpcs={"ethereum": "http://rpc.local"})
    await collector.collect()

    assert rows[0].deployed_at == datetime.fromtimestamp(block_ts, tz=UTC)
    factory._session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_age_collector_skips_when_address_missing():
    """No address -> no resolution attempt (e.g. Hyperliquid non-EVM)."""
    rows = [_protocol_row("Hyperliquid", address=None, chain="hyperliquid")]
    factory = _make_session_factory(rows)
    collector = ProtocolAgeCollector(factory, chain_rpcs={"ethereum": "http://rpc.local"})

    await collector.collect()
    assert rows[0].deployed_at is None
    factory._session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_age_collector_skips_when_no_rpc_for_chain():
    """Address known but chain has no configured RPC -> left unknown (honest)."""
    rows = [_protocol_row("GMX", address="0x...", chain="arbitrum")]
    factory = _make_session_factory(rows)
    collector = ProtocolAgeCollector(factory, chain_rpcs={"ethereum": "http://rpc.local"})

    await collector.collect()
    assert rows[0].deployed_at is None
    factory._session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_age_collector_skips_when_already_resolved():
    """deployed_at already set -> no work, no commit."""
    already = datetime(2023, 1, 1, tzinfo=UTC)
    rows = [_protocol_row("Aave V3", address="0x...", chain="ethereum", deployed_at=already)]
    factory = _make_session_factory(rows)
    collector = ProtocolAgeCollector(factory, chain_rpcs={"ethereum": "http://rpc.local"})

    await collector.collect()
    assert rows[0].deployed_at == already
    factory._session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_age_collector_skips_non_contract_address(patch_web3):
    """get_code empty at head (EOA / wrong chain) -> no deployed_at, no crash, no commit."""
    rows = [_protocol_row("Aave V3", address="0xEOA", chain="ethereum")]
    factory = _make_session_factory(rows)
    w3 = MagicMock()
    w3.eth.block_number = 10_000
    w3.eth.get_code = MagicMock(return_value=b"")  # empty at every block
    w3.eth.get_block = MagicMock(return_value={"timestamp": 1_700_000_000})
    patch_web3(w3)

    collector = ProtocolAgeCollector(factory, chain_rpcs={"ethereum": "http://rpc.local"})
    await collector.collect()

    assert rows[0].deployed_at is None
    factory._session.commit.assert_not_awaited()
