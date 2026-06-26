"""Alert engine and notification channel tests."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from types import SimpleNamespace, TracebackType
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest

from app.alerts.channels import (
    LoggingChannel,
    TelegramChannel,
    get_channel,
)
from app.alerts.engine import AlertEngine

# ── Helpers ─────────────────────────────────────────────────────────────────


class _FakeSessionCtx:
    """Async context manager that yields a pre-configured mock session."""

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


def _make_result(*, scalars_all: list | None = None, scalar_one: object = None) -> MagicMock:
    """Build a MagicMock execute-result with controlled scalars/scalar returns."""
    m = MagicMock()
    m.scalars.return_value.all.return_value = scalars_all or []
    m.scalar_one_or_none.return_value = scalar_one
    return m


def _market_row(asset: str = "USDC", market_type: str = "lending") -> SimpleNamespace:
    return SimpleNamespace(
        id=str(uuid4()), protocol_id=str(uuid4()), asset=asset, market_type=market_type
    )


def _lending_snap_row(
    *,
    market_id: str = "",
    borrow_apy: float = 5.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=str(uuid4()),
        market_id=market_id or str(uuid4()),
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        borrow_apy=borrow_apy,
        deposit_apy=8.0,
        utilization=0.7,
        tvl=1_000_000.0,
    )


def _funding_snap_row(
    *,
    market_id: str = "",
    annualized_funding: float = 15.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=str(uuid4()),
        market_id=market_id or str(uuid4()),
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        annualized_funding=annualized_funding,
    )


def _loop_calc_row(*, effective_yield: float = 8.0) -> SimpleNamespace:
    return SimpleNamespace(
        id=str(uuid4()),
        effective_yield=effective_yield,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _carry_calc_row(*, net_carry: float = 9.0) -> SimpleNamespace:
    return SimpleNamespace(
        id=str(uuid4()),
        net_carry=net_carry,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _existing_alert_row(alert_type: str = "borrow_apy_lt") -> SimpleNamespace:
    return SimpleNamespace(
        id=str(uuid4()),
        alert_type=alert_type,
        market_id="ignored",
        fired_at=datetime.now(UTC),
    )


# ── Channel tests ───────────────────────────────────────────────────────────


def test_get_channel_returns_telegram():
    ch = get_channel("telegram", bot_token="tok", chat_id="123")
    assert isinstance(ch, TelegramChannel)


def test_get_channel_returns_logging_for_unknown():
    ch = get_channel("discord")
    assert isinstance(ch, LoggingChannel)


def test_get_channel_returns_logging_for_log():
    ch = get_channel("log")
    assert isinstance(ch, LoggingChannel)


@pytest.mark.asyncio
async def test_logging_channel_logs_and_returns_true(caplog):
    ch = LoggingChannel()
    with caplog.at_level(logging.INFO):
        result = await ch.send("hello world")
    assert result is True
    assert "hello world" in caplog.text


@pytest.mark.asyncio
async def test_telegram_channel_sends_success():
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    ch = TelegramChannel(bot_token="tok123", chat_id="chat456", client=mock_client)
    result = await ch.send("test alert")

    assert result is True
    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottok123/sendMessage",
        json={"chat_id": "chat456", "text": "test alert"},
    )


@pytest.mark.asyncio
async def test_telegram_channel_returns_false_on_error():
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError(
        "bad", request=MagicMock(), response=MagicMock()
    ))
    mock_client.post = AsyncMock(return_value=mock_resp)

    ch = TelegramChannel(bot_token="tok123", chat_id="chat456", client=mock_client)
    result = await ch.send("test alert")

    assert result is False


# ── Engine tests ────────────────────────────────────────────────────────────
# The engine batches latest snapshot/calc queries into helper methods that
# return maps keyed by market_id. We patch those helpers directly so tests
# exercise threshold/dedup/channel logic without coupling to SQL mechanics.
# `session.execute` is only called for the Market query + dedup lookups.


def _session_factory_for_engine(session: MagicMock) -> MagicMock:
    factory = MagicMock()
    factory.return_value = _FakeSessionCtx(session)
    return factory


def _engine_with_session(
    session: MagicMock, *, thresholds: dict[str, float] | None = None
) -> AlertEngine:
    ch = AsyncMock(send=AsyncMock(return_value=True))
    return AlertEngine(
        session_factory=_session_factory_for_engine(session),
        channels={"log": ch},
        thresholds=thresholds
        or {"borrow_apy": 3.0, "funding_rate": 20.0, "loop_yield": 10.0, "net_carry": 12.0},
        cooldown_minutes=60,
    )


def _patch_batch_helpers(
    engine: AlertEngine,
    market: SimpleNamespace,
    *,
    lend: object | None = None,
    fund: object | None = None,
    loop_c: object | None = None,
    carry_c: object | None = None,
) -> None:
    """Patch the engine's batched query helpers to return fixed maps."""
    lend_map = {market.id: lend} if lend else {}
    fund_map = {market.id: fund} if fund else {}
    engine._latest_by_market = AsyncMock(side_effect=[lend_map, fund_map])
    engine._latest_loop_map = AsyncMock(return_value=({market.id: loop_c} if loop_c else {}))
    engine._latest_carry_map = AsyncMock(return_value=({market.id: carry_c} if carry_c else {}))


@pytest.mark.asyncio
async def test_engine_fires_borrow_apy_alert_when_below_threshold():
    """AlertEngine fires when borrow_apy (1%) < threshold (3%)."""
    market = _market_row(asset="USDC")
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    # Only the Market query + a single dedup query call session.execute.
    mock_session.execute = AsyncMock(
        side_effect=[
            _make_result(scalars_all=[market]),  # Markets query
            _make_result(scalar_one=None),       # Dedup → no prior alert
        ]
    )

    engine = _engine_with_session(mock_session)
    _patch_batch_helpers(engine, market, lend=_lending_snap_row(borrow_apy=1.0))
    alerts = await engine.evaluate()

    assert len(alerts) == 1
    assert alerts[0].alert_type == "borrow_apy_lt"
    assert alerts[0].triggered_value == 1.0
    assert alerts[0].threshold_value == 3.0
    mock_session.add.assert_called()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_engine_no_alert_when_borrow_apy_above_threshold():
    """No alert when borrow_apy (5%) > threshold (3%)."""
    market = _market_row(asset="USDC")
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[_make_result(scalars_all=[market])])

    engine = _engine_with_session(mock_session)
    _patch_batch_helpers(engine, market, lend=_lending_snap_row(borrow_apy=5.0))
    alerts = await engine.evaluate()

    assert len(alerts) == 0
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_engine_fires_funding_alert_when_above_threshold():
    """AlertEngine fires when annualized_funding (25%) > threshold (20%)."""
    market = _market_row(asset="ETH", market_type="perps")
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.execute = AsyncMock(
        side_effect=[
            _make_result(scalars_all=[market]),
            _make_result(scalar_one=None),  # dedup
        ]
    )

    engine = _engine_with_session(mock_session)
    _patch_batch_helpers(engine, market, fund=_funding_snap_row(annualized_funding=25.0))
    alerts = await engine.evaluate()

    assert len(alerts) == 1
    assert alerts[0].alert_type == "funding_rate_gt"
    assert alerts[0].triggered_value == 25.0


@pytest.mark.asyncio
async def test_engine_dedup_skips_within_cooldown():
    """Alert not re-fired when same alert_type+market_id exists within cooldown."""
    market = _market_row(asset="USDC")
    existing = _existing_alert_row("borrow_apy_lt")
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.execute = AsyncMock(
        side_effect=[
            _make_result(scalars_all=[market]),
            _make_result(scalar_one=existing),  # dedup → existing alert found
        ]
    )

    engine = _engine_with_session(mock_session)
    _patch_batch_helpers(engine, market, lend=_lending_snap_row(borrow_apy=1.0))
    alerts = await engine.evaluate()

    assert len(alerts) == 0
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_engine_channels_notified_on_fire():
    """Each configured channel.send() is called for each fired alert."""
    market = _market_row(asset="USDC")
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.execute = AsyncMock(
        side_effect=[
            _make_result(scalars_all=[market]),
            _make_result(scalar_one=None),
        ]
    )

    mock_chan = AsyncMock(send=AsyncMock(return_value=True))
    engine = AlertEngine(
        session_factory=_session_factory_for_engine(mock_session),
        channels={"telegram": mock_chan, "log": mock_chan},
        thresholds={"borrow_apy": 3.0},
        cooldown_minutes=60,
    )
    _patch_batch_helpers(engine, market, lend=_lending_snap_row(borrow_apy=1.0))

    await engine.evaluate()

    # Called once per channel (=2) for the single breached threshold
    assert mock_chan.send.call_count == 2


@pytest.mark.asyncio
async def test_engine_loop_yield_alert_fires():
    """Alert fires when effective_yield > threshold."""
    market = _market_row(asset="WETH")
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.execute = AsyncMock(
        side_effect=[
            _make_result(scalars_all=[market]),
            _make_result(scalar_one=None),
        ]
    )

    engine = _engine_with_session(mock_session)
    _patch_batch_helpers(engine, market, loop_c=_loop_calc_row(effective_yield=15.0))
    alerts = await engine.evaluate()

    assert len(alerts) == 1
    assert alerts[0].alert_type == "loop_yield_gt"
    assert alerts[0].triggered_value == 15.0


@pytest.mark.asyncio
async def test_engine_net_carry_alert_fires():
    """Alert fires when net_carry > threshold."""
    market = _market_row(asset="ETH", market_type="perps")
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.execute = AsyncMock(
        side_effect=[
            _make_result(scalars_all=[market]),
            _make_result(scalar_one=None),
        ]
    )

    engine = _engine_with_session(mock_session)
    _patch_batch_helpers(engine, market, carry_c=_carry_calc_row(net_carry=14.0))
    alerts = await engine.evaluate()

    assert len(alerts) == 1
    assert alerts[0].alert_type == "net_carry_gt"
    assert alerts[0].triggered_value == 14.0


@pytest.mark.asyncio
async def test_engine_no_markets_no_alerts():
    """No alerts when there are no markets in the DB."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.execute = AsyncMock(return_value=_make_result(scalars_all=[]))

    engine = _engine_with_session(mock_session)
    alerts = await engine.evaluate()

    assert len(alerts) == 0
    mock_session.add.assert_not_called()
