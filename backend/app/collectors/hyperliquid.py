"""Hyperliquid perpetuals adapter — fetches funding rates via REST API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger("defi_scanner")

# ── Constants ────────────────────────────────────────────────────────────────

_HYPERLIQUID_FUNDING_INTERVAL_HOURS = 1.0  # Hyperliquid funds hourly
_HOURS_PER_YEAR = 365 * 24  # 8760


def _annualize(funding_rate: float, interval_hours: float) -> float:
    """Compute annualized funding rate: rate * hours_per_year / interval_hours."""
    return funding_rate * _HOURS_PER_YEAR / interval_hours


# ── Adapter ──────────────────────────────────────────────────────────────────


class HyperliquidAdapter:
    """Fetches perpetual market funding rates from Hyperliquid's info API.

    Implements the FundingProvider protocol (from app.collectors.base).
    """

    def __init__(
        self,
        api_url: str = settings.HYPERLIQUID_API_URL,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        # ponytail: lazy client creation; add connection pooling config if needed
        self._client = httpx.AsyncClient(timeout=30)
        return self._client

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _retry_post(
        self, url: str, json: dict[str, object], max_retries: int = 3
    ) -> dict[str, Any]:
        """POST with exponential backoff retries. Returns parsed JSON response."""
        backoff = (1, 2, 4)
        last_exc: Exception | None = None
        client = await self._get_client()
        for attempt in range(max_retries):
            try:
                resp = await client.post(url, json=json)
                resp.raise_for_status()
                return resp.json()  # type: ignore[no-any-return]
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    wait = backoff[attempt]
                    logger.warning(
                        "Hyperliquid API attempt %d/%d failed, retrying in %ds: %s",
                        attempt + 1,
                        max_retries,
                        wait,
                        exc,
                    )
                    await asyncio.sleep(wait)
        logger.error("Hyperliquid API exhausted all %d retries: %s", max_retries, last_exc)
        raise last_exc  # type: ignore[misc]

    async def fetch_funding_rates(self) -> list[dict[str, object]]:
        """Fetch funding rates for all Hyperliquid perp markets.

        Implements FundingProvider protocol. Returns one dict per market
        with keys: asset, funding_rate, funding_interval_hours,
        annualized_funding, open_interest, volume_24h, mark_price,
        index_price, raw_payload.
        """
        data = await self._retry_post(
            f"{self._api_url}/info",
            {"type": "metaAndAssetCtxs"},
        )

        # Hyperliquid returns [meta_dict, asset_ctxs_list]
        # meta_dict = {"universe": [{"name": "BTC", ...}, ...]}
        # asset_ctxs_list = [{"funding": "0.0001", "openInterest": "...", ...}, ...]
        if not isinstance(data, list) or len(data) < 2:
            logger.error("Unexpected Hyperliquid API response shape: %s", type(data))
            return []

        meta = data[0]
        asset_ctxs = data[1]

        universe: list[dict[str, Any]] = meta.get("universe", []) if isinstance(meta, dict) else []
        if not isinstance(asset_ctxs, list):
            logger.error("Hyperliquid asset contexts is not a list: %s", type(asset_ctxs))
            return []

        if len(universe) != len(asset_ctxs):
            logger.warning(
                "Hyperliquid universe length (%d) != asset contexts length (%d)",
                len(universe),
                len(asset_ctxs),
            )

        results: list[dict[str, object]] = []
        for i, market_meta in enumerate(universe):
            if i >= len(asset_ctxs):
                break

            asset_name: str = market_meta.get("name", "")
            if not asset_name:
                continue

            ctx = asset_ctxs[i]
            if not isinstance(ctx, dict):
                logger.warning("Hyperliquid asset context at index %d is not a dict, skipping", i)
                continue

            try:
                funding_rate = float(ctx.get("funding", 0))
                interval_hours = _HYPERLIQUID_FUNDING_INTERVAL_HOURS
                annualized = _annualize(funding_rate, interval_hours)

                open_interest = float(ctx.get("openInterest", 0))
                volume_24h = float(ctx.get("dayNtlVlm", 0))
                mark_price = float(ctx.get("markPx", 0))
                index_price = float(ctx.get("oraclePx", 0))

                # ponytail: long/short ratio = 1.0 neutral; real ratio needs
                # openInterest size breakdown by side — Hyperliquid /info endpoint
                # doesn't provide this. Fetch from a separate endpoint or websocket
                # if directional OI matters.
                long_short_ratio: float = 1.0

                results.append({
                    "asset": asset_name,
                    "funding_rate": funding_rate,
                    "funding_interval_hours": interval_hours,
                    "annualized_funding": annualized,
                    "open_interest": open_interest,
                    "volume_24h": volume_24h,
                    "long_short_ratio": long_short_ratio,
                    "mark_price": mark_price,
                    "index_price": index_price,
                    "raw_payload": ctx,
                })
            except (ValueError, TypeError, KeyError) as exc:
                logger.warning(
                    "Failed to parse Hyperliquid market %s at index %d: %s",
                    asset_name,
                    i,
                    exc,
                )

        return results
