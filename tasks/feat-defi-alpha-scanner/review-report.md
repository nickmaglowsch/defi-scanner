# Code Review Report — DeFi Alpha Scanner MVP

## Summary

The vertical slice is structurally complete and the core deterministic calculations are well tested. However, it is **not ready to ship as-is** because several correctness/completeness gaps remain: the Docker stack does not run migrations, the looping calculator ignores on-chain LTV/liquidation-threshold data, the `/funding` endpoint cannot tell the UI which asset it is quoting, and the API has unbounded N+1 query patterns. These are fixable in a small follow-up pass.

## PRD Compliance

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 1 | Python/FastAPI backend, SQLAlchemy 2.0 async, Alembic, web3.py, httpx | ✅ Complete | uv + pyproject.toml; Python 3.13 used locally but Dockerfile pins 3.12. |
| 2 | Next.js 15 frontend | ⚠️ Partial | Next.js 16 installed (notes document this); build/lint pass. |
| 3 | PostgreSQL + TimescaleDB hypertables for snapshots | ✅ Complete | `001_initial.py` creates extension + hypertables; soft FKs on calc tables due to partition-key rule (documented). |
| 4 | 6 REST endpoints under `/api/v1` | ⚠️ Partial | All 6 exist, but `/funding` response lacks `asset`/`protocol` and ignores the `protocol` query param. |
| 5 | Looping/carry/ranker calculation engine | ⚠️ Partial | Functions are pure and tested, but orchestrator/API hard-code `max_ltv=0.8` and `liquidation_threshold=0.85` instead of using reserve config from `raw_payload`. |
| 6 | Provider-plugin interfaces (`LendingProvider`, `FundingProvider`) | ✅ Complete | `backend/app/collectors/base.py` defines both protocols. |
| 7 | Aave V3 + Hyperliquid collectors with retry resilience | ✅ Complete | 3 retries with exponential backoff; failures logged and skipped. |
| 8 | Alert engine + Telegram real channel, stub others | ✅ Complete | Telegram via httpx; other channels fall back to `LoggingChannel`. |
| 9 | CORS restricted to frontend origin | ✅ Complete | `allow_origins=[settings.FRONTEND_ORIGIN]`; no wildcard default. |
| 10 | Dashboard: home cards, loop/carry tables, funding chart | ⚠️ Partial | Funding card and chart selector show truncated UUIDs because `/funding` has no `asset` field. |
| 11 | Docker Compose local orchestration | ⚠️ Partial | Compose validates, but backend container never runs Alembic migrations. |
| 12 | TDD for calculations | ✅ Complete | `test_looping.py`, `test_carry.py`, `test_ranker.py` cover behavior and edge cases. |

**Compliance Score**: 7/12 fully met, 5 partial.

## Issues Found

### Critical (must fix before shipping)

_None. No data-loss, auth-inversion, or secret-exposure issues were found._

### Important (should fix)

- **`backend/app/calculations/orchestrator.py:46-54` and `backend/app/api/routes.py:344-352`**: Looping inputs `max_ltv=0.8` and `liquidation_threshold=0.85` are hard-coded, ignoring the actual Aave reserve configuration stored in `raw_payload`. This produces incorrect liquidation-distance and risk-score outputs for assets whose real parameters differ (e.g., WETH vs stablecoins). The fix is to source `ltv_pct` and `liquidation_threshold_pct` from the adapter output / raw payload and persist or pass them into `simulate_looping`.

- **`backend/app/api/routes.py:133-164`**: `/funding` accepts a `protocol` query parameter but never applies it. More importantly, the response schema `FundingSnapshotOut` has no `asset` or `protocol` field, so the dashboard cannot label funding markets. This is the root cause of the UUID display in the home card and chart selector. Add `asset` and `protocol` to the response (join `markets` + `protocols`) and implement the `protocol` filter.

- **`docker-compose.yml`** and **`backend/Dockerfile`**: The backend image starts Uvicorn directly and never runs `alembic upgrade head`. A fresh `docker compose up` will have an empty database and the app will not function. Add a migration step before app startup (e.g., an entrypoint script or a short-lived `migrate` service).

- **`backend/app/api/routes.py:291-445` and `backend/app/alerts/engine.py:44-56`**: Both endpoints and the alert engine issue per-row `db.get()` and per-snapshot subqueries in loops, creating N+1 query patterns. With 100+ markets this will be slow. Use `selectinload`/joined eager loads or batch the latest-snapshot subquery once per request/cycle.

- **`backend/app/calculations/carry.py:18`**: `risk_score` is unbounded. While the ranker min-max normalizes it, the raw value can exceed typical [0,1] expectations. This is documented but still a foot-gun for any consumer reading `carry_calculations.risk_score` directly. Consider clamping or documenting the scale explicitly.

### Minor (nice to fix)

- **`backend/tests/test_alerts.py:6,21,53` and `backend/tests/test_carry.py:183`**: `ruff check app/ tests/` reports unused imports (`timedelta`, `Alert`) and two E501 line-length violations in tests. The packet noted `ruff check app/` passes, but the project config does not exclude tests.

- **`frontend/src/components/loop-table.tsx:63,68` and `carry-table.tsx:55,60,65,70`**: Numeric columns use TanStack Table's `sortingFn: "alphanumeric"`, which can sort 100 < 9 lexicographically. Use `"basic"` or a numeric comparator.

- **`frontend/src/components/funding-chart.tsx:48` and `home-cards.tsx:95-96`**: Initial data fetches swallow errors with `.catch(() => {})`, hiding network/API failures from users. At minimum log or surface a retryable error.

- **`backend/app/schemas/responses.py:44-57`**: `FundingSnapshotOut` omits `funding_interval_hours` even though it is stored in the DB; include it for completeness.

- **`backend/app/api/routes.py:86-110`**: `/opportunities` silently ignores an invalid `type` parameter. Return `400` for values other than `all|loop|carry`.

- **`backend/app/api/routes.py:157`**: The asset filter on `/funding` does not restrict to `market_type='perp'`. Harmless today but wrong once a lending market shares an asset name with a perp.

- **`backend/app/collectors/hyperliquid.py:51-54`** and **`backend/app/alerts/channels.py:38`**: Injected/clients are never explicitly closed on shutdown. Add `aclose()` calls in the collector shutdown path or use a single shared `httpx.AsyncClient` with proper lifecycle.

- **`backend/tests/test_api.py`**: API tests mostly exercise empty-response paths. Add at least one happy-path test for `/looping` and `/opportunities` that verifies calculations are returned with expected fields.

- **`frontend/Dockerfile`**: Dev-only image is acceptable for the MVP but should be called out in README if not already.

## What Looks Good

- Clean separation between adapters, collectors, calculations, API, and alerts.
- Deterministic calculation functions are well isolated and thoroughly tested.
- Adapter retry logic uses exponential backoff and fails gracefully without crashing the collector loop.
- No secrets or RPC URLs are logged.
- CORS is not wildcard-open by default; it uses the configured frontend origin.
- TimescaleDB hypertable creation is guarded so it also works on plain PostgreSQL.
- Migrations are written manually and are consistent with the ORM models.

## Test Coverage

| Area | Tests Exist | Coverage Notes |
|------|-------------|----------------|
| Looping calc | Yes | 16 cases: leverage, zero spread, negative carry, max loops, safety buffer, zero capital, liquidation distance, risk score, LTV clamping. |
| Carry calc | Yes | 16 cases: positive/negative carry, zero inputs, risk formula, edge cases. |
| Ranker | Yes | 10 cases: ranking, ties, weights, penalty inversion, determinism. |
| Aave adapter | Yes | RAY conversion, config parsing, retry, utilization, collector upsert. |
| Hyperliquid adapter | Yes | Annualization, response parsing, malformed response handling, retry. |
| API | Partial | Smoke tests for all endpoints, but mostly empty-state; no happy-path calculation tests. |
| Alerts | Yes | Threshold firing, dedup cooldown, channel dispatch, no-market case. |
| Frontend | No | No automated UI tests (out of scope for MVP). |

**Test Coverage Assessment**: Calculation and adapter coverage is strong. API coverage is shallow and should be expanded before the endpoints are considered stable.

## Test Execution

| Check | Result | Details |
|-------|--------|---------|
| Test command discovered | Yes | `pytest` in `backend/` (from `pyproject.toml` dev deps). |
| Test suite run | Passed (109/109) | `uv run pytest -q` → 109 passed in ~15.7s. |
| TDD evidence in implementation notes | Yes | Tasks 05/06/07 document TDD, extra adequacy tests, and passing runs. |
| Lint | Partial | `uv run ruff check app/ tests/` → 4 issues in tests only. |

**Test Execution Assessment**: Backend tests are green. Fix the four ruff warnings in tests to keep CI clean.

## TDD Compliance

| Task | Tests Written | Tests Adequate | TDD Skipped Reason Valid | Notes |
|------|---------------|---------------|-------------------------|-------|
| Task 05 — Looping | Yes | Yes | N/A | Asserts on results, formulas, and edge cases; no trivial true assertions. |
| Task 06 — Carry | Yes | Yes | N/A | Covers sign/negative cases and risk-score formula. |
| Task 07 — Ranker | Yes | Yes | N/A | Covers ranking, ties, weights, penalty inversion. |

**TDD Assessment**: TDD was applied correctly to the three pure-calculation tasks.
**Test Adequacy**: 36/36 meaningful. No weak type/existence-only assertions were flagged in the calc suite.
**Mocking Discipline**: Adapter tests mock at the system boundary (httpx client, web3 contract functions). API/alert tests mock the DB session dependency. No internal modules or the code-under-test itself are mocked.

## Implementation Decision Review

| Task | Decisions Documented | Decisions Sound | Flags |
|------|---------------------|----------------|-------|
| Task 01 — Scaffold | Yes | Mostly | Next.js 16 / Tailwind v4 is bleeding edge but documented as a risk. |
| Task 02 — DB schema | Yes | Yes | Soft FKs for hypertables are the correct TimescaleDB pattern. |
| Task 03 — Aave adapter | Yes | Yes | Storing raw integer amounts is correct for ratio math. |
| Task 04 — Hyperliquid adapter | Yes | Yes | Neutral `long_short_ratio` is documented. |
| Task 05/06/07 — Calcs/API | Yes | Partial | Default/hard-coded looping LTV params are not sourced from on-chain data — a real correctness gap. |
| Task 08 — Alerts | Yes | Yes | Per-market queries are acknowledged as a future scaling concern. |
| Task 09 — Frontend | Yes | Partial | The `market_id` UUID fallback is documented, but it is still a dashboard UX/completeness issue. |

**Decision Assessment**: Most documented decisions are sound. The two decisions that need revisiting are (1) ignoring on-chain LTV/liquidation threshold in loop calculations, and (2) shipping `/funding` without an asset field.

## Recommendations

1. **Add Alembic migration step to the Docker entrypoint** so `docker compose up` produces a working stack.
2. **Source real `ltv_pct` and `liquidation_threshold_pct`** from the Aave adapter output / `raw_payload` and thread them through `simulate_looping` in both the orchestrator and API fallback path.
3. **Enrich `/funding`** with `asset` and `protocol` fields and implement the `protocol` query-param filter so the dashboard can label funding markets.
4. **Batch the per-market lookups** in `/looping`, `/opportunities`, and the alert engine to eliminate N+1 queries.
5. **Fix the ruff warnings** in tests and switch TanStack Table numeric columns to a numeric sorting function.
6. **Add at least one API happy-path test** that exercises `/looping` and `/opportunities` with mocked snapshots and asserts on computed output fields.
