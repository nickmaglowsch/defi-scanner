"""Notification channels for the alert engine.

Real: Telegram Bot API via httpx.
Stub: LoggingChannel drops message at INFO level.

ponytail: real email/slack/discord impl goes here.
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

logger = logging.getLogger("defi_scanner")


class NotificationChannel(Protocol):
    """Protocol for alert notification delivery channels."""

    async def send(self, message: str) -> bool:
        """Deliver a message. Returns True on success, False on failure."""
        ...


class TelegramChannel:
    """Sends alerts via Telegram Bot API (httpx POST)."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._client = client or httpx.AsyncClient()

    async def send(self, message: str) -> bool:
        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        try:
            resp = await self._client.post(
                url, json={"chat_id": self._chat_id, "text": message}
            )
            resp.raise_for_status()
            return True
        except Exception:
            logger.exception("Telegram notification failed")
            return False


class LoggingChannel:
    """Stub channel that logs messages at INFO level.

    ponytail: real email/slack/discord impl goes here.
    """

    async def send(self, message: str) -> bool:
        logger.info("Alert notification: %s", message)
        return True


def get_channel(name: str, bot_token: str = "", chat_id: str = "") -> NotificationChannel:
    """Factory: returns a NotificationChannel instance by name."""
    if name == "telegram":
        return TelegramChannel(bot_token=bot_token, chat_id=chat_id)
    return LoggingChannel()
