"""Alert engine — threshold evaluation + notification dispatch.

Background task ``run_alerts`` is wired into the collector runner so it
shares the shutdown lifecycle without touching main.py.
"""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.db.session import async_session_factory

logger = logging.getLogger("defi_scanner")


async def run_alerts(shutdown_event: asyncio.Event) -> None:
    """Background task: evaluate alert thresholds on a schedule.

    Creates an AlertEngine with configured channels and runs
    ``evaluate()`` every ALERT_INTERVAL_SECONDS until shutdown.
    """
    from app.alerts.channels import get_channel
    from app.alerts.engine import AlertEngine

    channels: dict[str, object] = {}
    if settings.TELEGRAM_BOT_TOKEN:
        channels["telegram"] = get_channel(
            "telegram",
            bot_token=settings.TELEGRAM_BOT_TOKEN,
            chat_id=settings.TELEGRAM_CHAT_ID,
        )
    else:
        logger.warning("TELEGRAM_BOT_TOKEN not configured; telegram alerts disabled")
    channels["log"] = get_channel("log")

    thresholds = {
        "loop_yield": settings.ALERT_LOOP_YIELD_THRESHOLD,
        "funding_rate": settings.ALERT_FUNDING_RATE_THRESHOLD,
        "net_carry": settings.ALERT_NET_CARRY_THRESHOLD,
        "borrow_apy": settings.ALERT_BORROW_APY_THRESHOLD,
    }

    engine = AlertEngine(
        async_session_factory,
        channels,
        thresholds,
        settings.ALERT_COOLDOWN_MINUTES,
    )

    logger.info(
        "Alert engine started (interval=%ds, cooldown=%dm, channels=%s)",
        settings.ALERT_INTERVAL_SECONDS,
        settings.ALERT_COOLDOWN_MINUTES,
        list(channels),
    )

    while not shutdown_event.is_set():
        try:
            await engine.evaluate()
        except Exception:
            logger.exception("Alert evaluation failed, will retry")
        try:
            await asyncio.wait_for(
                shutdown_event.wait(), timeout=settings.ALERT_INTERVAL_SECONDS
            )
        except TimeoutError:
            pass  # interval elapsed — loop again
