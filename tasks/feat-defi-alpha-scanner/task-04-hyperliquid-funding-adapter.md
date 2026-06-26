# Task 04: Hyperliquid Funding Adapter & Collector

## Objective
Define the `FundingProvider` protocol interface, implement the Hyperliquid REST adapter via httpx, and build the funding collector service that writes funding snapshots to the database on a schedule.

## Context
Hyperliquid's public REST API (`api.hyperliquid.xyz/info`) provides perpetual market metadata including funding rate, open interest, and price data via a single POST endpoint. This task is the sibling of task-03 (Aave adapter) — same pattern, different data source. The adapter implements the `FundingProvider` protocol defined in task-03's `base.py`.

**Quick Context**:
- Hyperliquid API: POST `https://api.hyperliquid.xyz/info` with `{"type": "metaAndAssetCtxs"}` returns all perp markets + context (funding, open interest, mark price, index price, etc.).
- Funding rate in response is decimal per interval (hourly). Annualized = `rate * (365 * 24 / interval_hours)`.
- Models from task-02: `Protocol`, `Market`, `FundingSnapshot`.
- httpx async client for HTTP calls.

## Target Files
- `backend/app/collectors/hyperliquid.py`
- `backend/app/collectors/funding.py`
- `backend/tests/test_hyperliquid_adapter.py`

## Dependencies
- task-02 (needs models + DB session)
- task-03 (uses `FundingProvider` protocol from `base.py`; follows collector wiring pattern in `main.py` established by task-03)

## Steps
1. Write `backend/app/collectors/hyperliquid.py`:
   - Class `HyperliquidAdapter` implementing `FundingProvider` (from `app.collectors.base`).
   - `__init__` takes `api_url` (default from config), `httpx.AsyncClient` (optional — creates own).
   - `async fetch_funding_rates()`:
     - POST to `{api_url}/info` with `{"type": "metaAndAssetCtxs"}`.
     - Parse response: `response[0]["universe"]` → list of market metadata (name, szDecimals, etc.), `response[1]` → list of asset contexts (funding, openInterest, markPx, indexPx, dayNtlVlm, prevDayPx, etc.) — same length + order as universe.
     - For each market in universe, pair with asset context by index.
     - Compute: `funding_rate` = raw funding decimal from context, `funding_interval_hours` = 1.0 (Hyperliquid funds hourly), `annualized_funding = funding_rate * 8760 / 1.0` (8760 = 365*24).
     - Compute `long_short_ratio` from open interest data (Hyperliquid provides `openInterest` but ratio may need separate endpoint or approximation — use `1.0` as neutral default with a `# ponytail:` comment noting the real ratio needs additional data).
     - Return list of dicts: asset (market name, e.g. "BTC"), funding_rate, funding_interval_hours, annualized_funding, open_interest, volume_24h, mark_price, index_price.
   - Retry wrapper: same pattern as Aave adapter (3 retries, 1s/2s/4s backoff).
   - Handle Hyperliquid-specific errors: non-200 response, missing keys.
2. Write `backend/app/collectors/funding.py`:
   - `FundingCollector` service class (mirrors `LendingCollector` from task-03):
     - Takes async DB session factory, `FundingProvider` instance.
     - `async collect()`: calls `provider.fetch_funding_rates()`, upserts `Protocol` row (name="Hyperliquid", type="derivatives", chain="hyperliquid"), upserts `Market` rows (one per perp asset, market_type="perp"), inserts `FundingSnapshot` rows with all fields + `raw_payload` = JSON dump of raw API response.
     - Log snapshot count and errors.
3. Wire funding collector into `backend/app/main.py`:
   - Extend the lifespan loop that task-03 created (lending collector is already wired). Add funding collector alongside it:
     ```python
     hyperliquid = HyperliquidAdapter(settings.HYPERLIQUID_API_URL)
     funding_collector = FundingCollector(session_factory, hyperliquid)
     asyncio.create_task(_run_collector_loop(funding_collector.collect, settings.COLLECTOR_INTERVAL_SECONDS, stop_event))
     ```
   - Both collectors run independently with their own retry/skip cycles.
   - Since task-03 already set up the `_run_collector_loop` helper and `stop_event`, reuse those — only add the new task spawn.
4. Write `backend/tests/test_hyperliquid_adapter.py`:
   - Test with mocked `httpx.AsyncClient`: mock `post()` to return a sample `metaAndAssetCtxs` response (grab a small one or fabricate 2-3 markets).
   - Test annualized funding calculation: raw rate 0.0001 → `0.0001 * 8760 = 0.876` (87.6% APR).
   - Test retry: same pattern as Aave tests.
   - Test that `fetch_funding_rates()` returns correct list length and field names.
   - Test empty response handling (no markets returned).
   - Test invalid JSON response handling.

## Acceptance Criteria
- [ ] `HyperliquidAdapter.fetch_funding_rates()` returns one dict per Hyperliquid perp market with all expected fields
- [ ] Annualized funding = `funding_rate * 8760 / interval_hours` (e.g., 0.01% hourly → 87.6% annualized)
- [ ] Retry with exponential backoff works (same pattern as Aave adapter)
- [ ] `FundingCollector.collect()` writes `Protocol`, `Market`, and `FundingSnapshot` rows to DB
- [ ] `raw_payload` column contains the full API response as JSON
- [ ] Upsert prevents duplicate protocol/market rows
- [ ] All unit tests pass: `pytest tests/test_hyperliquid_adapter.py -v`
- [ ] Both collectors run concurrently in FastAPI lifespan (visible in startup logs)
- [ ] `ruff check` passes on all new files
