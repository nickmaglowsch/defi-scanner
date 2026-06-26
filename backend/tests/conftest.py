"""Shared test fixtures for DeFi Scanner."""

from __future__ import annotations

from types import TracebackType
from unittest.mock import AsyncMock, MagicMock

import pytest
from web3 import Web3 as _RealWeb3

# ── Helpers ─────────────────────────────────────────────────────────────────


class _FakeSessionCtx:
    """A real async context manager that yields a pre-configured mock session."""

    def __init__(self, session: MagicMock) -> None:
        self._session = session

    async def __aenter__(self) -> MagicMock:
        return self._session

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        pass


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_web3_init(mocker) -> None:  # type: ignore[no-untyped-def]
    """Prevent Web3 constructor from making real HTTP calls."""

    def _fake_init(self_w3, provider=None, **kw):  # type: ignore[no-untyped-def]
        self_w3.eth = MagicMock()
        self_w3.eth.chain_id = 1

    mocker.patch.object(_RealWeb3, "__init__", _fake_init)


@pytest.fixture
def mock_db_session_factory() -> MagicMock:  # type: ignore[no-untyped-def]
    """Return a mock session factory.

    Calling the factory returns a _FakeSessionCtx that yields a mock session
    with async mocks for execute/commit/flush/rollback.
    """
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.execute.return_value = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    mock_session.get = AsyncMock()
    mock_session.get.return_value = None
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.add = MagicMock()

    factory = MagicMock()
    factory.return_value = _FakeSessionCtx(mock_session)
    factory._mock_session = mock_session  # ponytail: expose for test assertions
    return factory


@pytest.fixture
def mock_provider(mocker) -> AsyncMock:  # type: ignore[no-untyped-def]
    """AsyncMock LendingProvider — fetch_reserves returns empty list by default."""
    provider = mocker.AsyncMock()
    provider.fetch_reserves.return_value = []
    return provider
