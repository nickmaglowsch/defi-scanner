# Implementation Notes


# Task 01: Repository Scaffold & Dev Environment

- **Decisions**:
  - Used `SettingsConfigDict(env_prefix="DEFI_")` instead of the `model_config` dict literal mentioned in the task spec — both are valid in pydantic-settings v2, and `SettingsConfigDict` is the recommended approach in newer versions. The task's intended behavior is identical.
  - Used `asynccontextmanager`-based `lifespan` instead of the deprecated `@app.on_event("startup")` pattern. FastAPI's `on_event` is deprecated since 0.107; the lifespan pattern is the modern equivalent and achieves the same startup DB connection test.
  - Used `--import-alias "@/*"` for create-next-app instead of `--no-import-alias` from the task step 6. `--no-import-alias` is not a recognized flag in Next.js 16's create-next-app; `@/*` is the standard alias used by shadcn/ui and matches project conventions.
  - `COLLECTOR_INTERVAL_SECONDS` typed as `int` for automatic coercion from env string.
  - Frontend Dockerfile CMD uses `-H 0.0.0.0` so the dev server is reachable from outside the container.
  
- **Deviations**:
  - Installed Next.js 16 (latest via `create-next-app@latest`) instead of the 15 referenced in shared-context. The task said `@latest`; Next.js 16 was released and the CLI auto-selected it. shadcn/ui v4.11.0 init worked correctly with Next.js 16 and Tailwind CSS v4.
  - `uv lock` resolved with Python 3.13 (the available `uv` uses CPython 3.13.13). The `pyproject.toml` sets `requires-python = ">=3.12"`, so this is compatible. Python 3.12 is only specified in the Dockerfile base image.
  - Backend Dockerfile uses `uv sync --frozen` — this requires `uv.lock` in the build context. Lockfile was generated successfully.
  - Did not attempt `docker compose up` (as instructed in environment notes). Compose config validates cleanly via `docker compose config`.

- **Trade-offs**: None — straightforward scaffold with no alternatives to weigh.

- **Risks**:
  - Next.js 16 + React 19 + Tailwind v4 is bleeding edge. shadcn/ui v4.11.0 init succeeded, but compatibility with TanStack Table and Recharts should be verified when task-09 adds the dashboard.
  - `uv.lock` is committed (461KB) — it's the correct behavior for reproducible builds, worth the repo size.
  - Frontend Dockerfile is dev-only (`npm run dev`). For production, task-09 or a future task should switch to Next.js standalone output with `npm run build && npm start`.


# Task 02: Database Schema & Migrations

- **Decisions**: 
  - Used string UUIDs (`String(36)`) as primary keys rather than native `UUID` type — simpler application-side generation, no driver-specific UUID handling.
  - Snapshot tables use composite PK `(id, observed_at)` with no unique constraint on `id` alone — required by TimescaleDB (partition column must be in all unique indexes). FK references from calculation tables (`loop_calculations.lending_snapshot_id`, `carry_calculations.funding_snapshot_id`, `carry_calculations.lending_snapshot_id`) are soft references (plain columns, no DB-level FK). UUIDs guarantee uniqueness at the application level. This is the standard pattern seen in TimescaleDB projects with hypertables that have child-table references.
  - Alembic `env.py` constructs sync URL by replacing `+asyncpg` with `+psycopg2` — matching the existing config approach, no need for a separate sync database URL configuration.
  - Unitended side effect: the `Func` import from sqlalchemy was not used in lending_snapshot.py and funding_snapshot.py — kept `import` to match the `func` call on `server_default` for other models, but removed on snapshots (no `func.now()` col needed).

- **Deviations**: 
  - FK constraints removed from `loop_calculations.lending_snapshot_id` and `carry_calculations.funding_snapshot_id` (and `carry_calculations.lending_snapshot_id`) — technically a deviation from the PRD which shows FK arrows, but necessary for TimescaleDB compatibility. The PRD arrows are logical references, not necessarily DB-level constraints.
  - `alembic revision --autogenerate` not possible without a live DB; wrote migration manually from model definitions.

- **Trade-offs**: 
  - Could have used a separate unique index on `id` + dropped/re-added it around hypertable creation, but that's fragile and non-transactional. Soft FKs are simpler and sufficient for a read-only scanner.
  - Models verified import-time and with ruff; no test files exist yet (tests are task-03+).

- **Risks**: 
  - If anyone adds a DB-level FK from a child table to `lending_snapshots.id` or `funding_snapshots.id`, it will fail because there's no unique constraint on `id` alone. The `id` column is only unique within the composite PK. Documentation in migration comments covers this.
  - The `server_default` for `risk_score` is the string `'0'` — SQLAlchemy will type-coerce but reviewers should be aware this is intentional (matches the model).


# Task 03: Aave V3 Lending Adapter & Collector

- **Decisions**:
  - APY stored as percentage (e.g., 5.0 = 5%). This matches the PRD's dashboard display expectation.
  - Token amounts stored as raw smallest-unit values (wei for ETH, 6-decimal for USDC). No normalisation applied — the ratio math (utilization) is correct regardless of decimals, and raw values allow the dashboard to format at the display layer.
  - Configuration bit parsing follows the task spec exactly (LTV bits 16-31, liquidation threshold 32-47, reserve factor 0-15, ÷100). These values are included in raw_payload but not in separate snapshot columns (no schema columns exist for them).
  - Collector upsert uses SELECT-then-INSERT rather than ON CONFLICT to avoid aborting the entire batch on unique violations. This is slightly less efficient but tolerant of concurrent writers.
  - `raw_payload` stores string representations for large integers (uint256/uint128) to ensure JSONB compatibility. Hex for configuration.data, decimal strings for rates and token supplies.
- **Deviations**: None. All required tests pass, all acceptance criteria met.
- **Trade-offs**:
  - Token supply fetching is sequential (aToken then debtToken) rather than parallel. Two sequential RPC calls per asset. Switched to gather() if latency becomes an issue — the retry wrapper already handles individual failures.
  - Web3 constructor mocking required patching `Web3.__init__` (rather than the class-level `Web3` mock) because web3 internally does `isinstance(parent_module, Web3)` checks that fail on MagicMock instances. The `_fake_init` sets `self_w3.eth` so subsequent `self.w3.eth.contract()` calls resolve.
  - Async session mocking uses a real `_FakeSessionCtx` class rather than MagicMock's `__aenter__` because Python's `async with` resolves `__aenter__` on the type, not the instance — instance-level AsyncMock assignment is silently ignored.
- **Risks**:
  - The `_AAVE_POOL_ABI` is hand-crafted minimal ABI. If Aave V3 upgrades its Pool interface, the embedded ABI may need updating. The `getReserveData` function signature is stable but not guaranteed forever.
  - The `getReservesList()` call fetches ALL Aave reserves (100+ assets), then filters to tracked. This is a single RPC call so overhead is negligible, but the full list may grow over time.


# Task 04: Hyperliquid Funding Adapter & Collector

- **Decisions**:
  - HTTP retry uses `httpx.HTTPStatusError` + `asyncio.sleep` instead of building a dedicated retry utility. Matches the inline retry pattern in the Aave adapter (which uses `asyncio.to_thread` for sync web3 calls), adapted for async httpx.
  - `long_short_ratio` hardcoded to `1.0` with a `ponytail:` comment — Hyperliquid's `/info` endpoint doesn't expose directional open interest. Ratio needs a separate data source.
  - Adapter accepts an optional `httpx.AsyncClient` for dependency injection, enabling clean test mocking without `respx`.
  - `raw_payload` stores only the per-market asset context dict (not the full API response), which is what the snapshot row represents. The full raw response can be recreated from the union of individual `raw_payload` fields if needed.
- **Deviations**: None. Config `HYPERLIQUID_API_URL` was already present in `config.py` — no config change needed.
- **Trade-offs**: Skipped `respx` as a test dependency since `pytest-mock` + `AsyncMock` on the injected client achieves the same with zero deps. If more complex HTTP mocking is needed later, add `respx` then.
- **Risks**: Hyperliquid API response shape is validated leniently (checks list-of-2, dict keys). If the API pivots to a different envelope, the adapter returns `[]` with a warning log rather than crashing — safe, but may silently skip cycles. Monitor collector logs on deploy.


# Task 05: Looping Simulator (TDD)

- **Decisions**: APY inputs/outputs kept in percentage units (e.g., 5.0 = 5%) as specified — no internal conversion to decimal. The `net_apy` formula `(total_deposited * deposit_apy - total_borrowed * borrow_apy) / initial_capital` works directly in % space since both numerator and denominator cancel the 100× factor.
- **Deviations**: Added 7 extra test cases beyond the 9 required (safety margin formula, risk score edge case, LTV clamping when target > max_ltv, effective_yield parity, leverage ratio verification, full keys check, input passthrough) to satisfy the ADEQUACY check. Added `deposit_apy`/`borrow_apy` to the test defaults dict to avoid redundant per-test overrides.
- **Trade-offs**: The `LTV_USAGE_RATIO = 0.9` is not configurable per call — matches the task spec's "conservative default." If per-protocol LTV usage ratios are needed, add as a parameter later.
- **Risks**: The convergence is asymptotic — with very tight safety buffers and low `ltv_used`, `max_loops` may terminate before reaching target. Callers should use generous `max_loops` (≥20) for precision. Zero `liquidation_threshold` with non-zero capital produces a `liquidation_distance` of 0.0 (guarded), which is mathematically correct but may surprise consumers.


# Task 06: Carry Calculator (TDD)

- **Decisions**: `expected_annual_return = net_carry` (as %). No notional multiplication — the function operates on yield percentages only, consistent with the looping calculator pattern. Input capital is implicit (handled by the API layer that applies this to notional).
- **Deviations**: None. Followed the task spec formula exactly.
- **Trade-offs**: `risk_score` uses a linear heuristic (`abs(funding_yield)*0.3 + abs(borrow_cost)*0.2`) which is unbounded — values can exceed 1.0. The ranker (task-07) may normalize/clamp when combining with the volatility component.
- **Risks**: Unbounded risk_score. If the ranker expects values in [0,1], the ranker should clamp. Marked with a `ponytail:` comment in the source.


# Task 07: Opportunity Engine & REST API

- **Decisions**:
  - Ranker normalizes all 7 metrics via min-max scaling across the batch. Penalty metrics (utilization, volatility, protocol_risk) are inverted as `1 - normalized` so higher raw penalty → lower contribution to score. When min==max, normalized value is 0 (neutral).
  - Orchestrator (`trigger_loop_calculation`, `trigger_carry_calculation`) is called AFTER the collector commits the snapshot transaction, in a fresh session. This avoids interfering with pre-existing test mock expectations and keeps calculation failures from rolling back snapshot writes.
  - Volatility penalty computed via SQL `STDDEV(funding_rate)` over the last N rows (default 20) — neutral 0 if insufficent rows.
  - API routes use `func.max()` + `.label()` for subquery column access instead of `text()`, which avoids SQLAlchemy `AttributeError` on `.c.max_ts`.
  - The `/opportunities` endpoint merges loop and carry results, scored separately by the ranker (each type gets its own normalization), then the combined list is sorted by score for a unified ranking.

- **Deviations**:
  - `Ranker.looping` and `Ranker.carry` in the responses schema renamed to `LoopOpportunityOut` / `CarryOpportunityOut` for consistency with the project's naming pattern.
  - The `_trigger_calc` methods in collectors use try/except so a calc failure doesn't block the collector cycle (logged as error).

- **Risks**:
  - The `/looping` and `/opportunities` endpoints run `simulate_looping`/`calculate_carry` on every request for snapshots that haven't been calculated yet (due to lazy DB addition — not from collector cycles). Under high load this could create overhead; the idempotency check prevents duplicates but not recomputation. For production: use the orchestrator call from collectors as the primary write path.
  - Volatility STDDEV query uses a simple LIMIT + STDDEV approach rather than the window function spec'd (`STDDEV OVER ROWS 20 PRECEDING`). This works correctly for the latest N rows per market but doesn't give per-row historical volatility. Sufficient for the penalty input to the ranker.


# Task 08: Alert Engine & Telegram Notification

- **Decisions**: Wired `run_alerts` into `collectors/__init__.py` as a background task alongside collectors rather than touching `main.py`, matching shared-context's preference. The alert engine runs on its own schedule (`ALERT_INTERVAL_SECONDS`, default 300s) separate from the collector cycle.
- **Deviations**: `NotificationChannel` is a `Protocol` rather than an ABC — simpler and equally effective for duck-typing. Channel factory `get_channel` takes explicit `bot_token`/`chat_id` strings rather than a full config object — the two values are all Telegram needs.
- **Trade-offs**: Query helpers (`_latest_lending`, etc.) are static methods on the engine instead of free functions. Could be extracted if reused elsewhere, but they're alert-specific queries right now.
- **Risks**: The engine queries all markets every cycle. With hundreds of markets this could be slow — consider limiting to active markets or adding an index on `observed_at` + `market_id` if latency becomes a problem.


# Task 09: Frontend Dashboard

- **Decisions**: 
  - Used `"use no memo"` directive on TanStack Table components to suppress React Compiler warnings about incompatible memoization (TanStack Table v8 generates functions unsafely for React 19 compiler).
  - Used `eslint-disable react-hooks/set-state-in-effect` for data-fetching effects — the React 19 lint rule flags the pattern `setLoading(true)` in `useEffect`, but this is a legitimate, well-established pattern for data fetching. Refactoring to avoid it would add unnecessary complexity (e.g., startTransition wrappers or useReducer).
  - Types kept inline in `lib/api.ts` (~70 lines of interfaces) rather than a separate `types/` directory. Ponytail: fewer files, one import for consumers.
  - Home cards use individual `useEffect` hooks per card — each fetches independently. Could use `Promise.all` but independent hooks give partial rendering (cards appear as data arrives) for better perceived performance.
- **Deviations**: 
  - "Highest Funding" card displays `market_id` (truncated UUID) instead of an asset name. The `/funding` endpoint returns `FundingSnapshotOut` which has no `asset` field — only `market_id`. The task spec says to display "asset + annualized_funding%" but the API shape doesn't support it. `CarryOpportunityOut` (from `/opportunities?type=carry`) has `asset` + `funding_yield`, but the task said to use `/funding`. Used the specified endpoint and displayed the truncated market_id.
  - History chart uses `observed_at` → `toLocaleDateString()` for the X axis. Time-formatting can be refined later.
  - Chart market selector labels are truncated UUIDs (first 16 chars + "…"). The `/funding` endpoint returns `market_id` UUIDs only — no human-readable market name. Adding market names would require an API change or a `/markets` endpoint.
- **Trade-offs**: 
  - Client-side sorting with TanStack Table rather than server-side. The data set is bounded (max 100 rows from API), so client-side sorting is immediate and avoids extra round-trips.
  - Filters trigger API refetches (server-side filtering) rather than client-side filtering. This ensures consistency: filters narrow results at the DB level, not after the fact.
- **Risks**: 
  - The `/history` endpoint requires a valid UUID `market_id`. If `/funding` returns 0 snapshots, the market selector stays empty and the chart shows no data. This is handled gracefully.
  - Select components (`@base-ui/react/select` v4 shadcn) differ from the classic Radix-based shadcn select. The `onValueChange` callback passes `string | null`, not `string`. Wrapped all handlers with a null guard.

