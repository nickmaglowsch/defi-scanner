"""dYdX v4 perpetuals adapter — fetches funding rates via the public indexer."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger("defi_scanner")

# ── Constants ────────────────────────────────────────────────────────────────

# ponytail: dYdX v4 pays funding every hour. Annualization uses 365 * 24 hours.
_DYDX_FUNDING_INTERVAL_HOURS = 1.0
_HOURS_PER_YEAR = 365 * 24  # 8760


def _annualize(funding_rate: float, interval_hours: float) -> float:
    """Compute annualized funding rate: rate * hours_per_year / interval_hours."""
    return funding_rate * _HOURS_PER_YEAR / interval_hours


def _asset_from_ticker(ticker: str) -> str:
    """Extract base asset from a dYdX ticker like 'BTC-USD'."""
    return ticker.split("-")[0] if "-" in ticker else ticker


# ── Adapter ──────────────────────────────────────────────────────────────────


class DydxAdapter:
    """Fetches perpetual market funding rates from dYdX v4's indexer API.

    Implements the FundingProvider protocol (from app.collectors.base).
    """

    def __init__(
        self,
        api_url: str = settings.DYDX_INDEXER_URL,
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

    async def _get(self, path: str) -> dict[str, Any]:
        """GET with status check. Returns parsed JSON response."""
        client = await self._get_client()
        resp = await client.get(f"{self._api_url}{path}")
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    async def fetch_funding_rates(self) -> list[dict[str, object]]:
        """Fetch funding rates for all dYdX v4 perp markets.

        Implements FundingProvider protocol. Returns one dict per active market
        with keys: asset, funding_rate, funding_interval_hours,
        annualized_funding, open_interest, volume_24h, mark_price,
        index_price, long_short_ratio, raw_payload, chain, protocol,
        market_type.
        """
        data = await self._get("/v4/perpetualMarkets")

        # dYdX returns {"markets": {"BTC-USD": {...}, ...}}
        if not isinstance(data, dict):
            logger.error("Unexpected dYdX API response shape: %s", type(data))
            return []

        markets = data.get("markets")
        if not isinstance(markets, dict):
            logger.error("dYdX markets field is not a dict: %s", type(markets))
            return []

        results: list[dict[str, object]] = []
        for ticker, market in markets.items():
            if not isinstance(market, dict):
                logger.warning("dYdX market %s is not a dict, skipping", ticker)
                continue

            if market.get("status") != "ACTIVE":
                # ponytail: skip delisted/inactive markets; dYdX also has
                # INITIALIZING and CLOSED statuses.
                continue

            asset = _asset_from_ticker(ticker)
            if not asset:
                continue

            try:
                funding_rate = float(market.get("nextFundingRate", 0))
                interval_hours = _DYDX_FUNDING_INTERVAL_HOURS
                annualized = _annualize(funding_rate, interval_hours)

                open_interest = float(market.get("openInterest", 0))
                volume_24h = float(market.get("volume24H", 0))
                index_price = float(market.get("oraclePrice", 0))

                # ponytail: dYdX indexer /v4/perpetualMarkets does not expose a
                # mark price distinct from oracle; use oracle as the best proxy.
                mark_price = index_price

                # ponytail: long/short OI breakdown is not available on the
                # public markets endpoint; default to neutral 1.0.
                long_short_ratio: float = 1.0

                results.append({
                    "asset": asset,
                    "funding_rate": funding_rate,
                    "funding_interval_hours": interval_hours,
                    "annualized_funding": annualized,
                    "open_interest": open_interest,
                    "volume_24h": volume_24h,
                    "long_short_ratio": long_short_ratio,
                    "mark_price": mark_price,
                    "index_price": index_price,
                    "raw_payload": market,
                    "chain": "dydx",
                    "protocol": "dYdX",
                    "market_type": "perp",
                })
            except (ValueError, TypeError, KeyError) as exc:
                logger.warning("Failed to parse dYdX market %s: %s", ticker, exc)

        return results
