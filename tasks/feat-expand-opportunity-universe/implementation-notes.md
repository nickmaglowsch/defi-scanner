# Implementation Notes

## Task 05 — New Lending Adapters Batch 2 (Fluid, Moonwell, Compound, Silo)

- Fluid: Used `https://api.fluid.instadapp.io/v2/{chainId}/vaults` (verified live). Rates in basis points; asset named `supplySymbol/borrowSymbol`.
- Moonwell: Used `https://api.moonwell.fi/v1/markets?chainId={chainId}` (verified live). APYs already percent.
- Compound: `NotImplementedError` — V3 (Comet) has no public REST API; COMP rewards require on-chain `CometRewards` contract.
- Silo: `NotImplementedError` — no stable public REST API; TheGraph subgraph needs paid API key. SiloLens contract is the upgrade path.
- Risk: Fluid API is unofficial/undocumented — monitor for 404s if Instadapp restructures URL scheme.

## Task 06 — notes file produced by prior run (see notes/task-06.md)

## Task 07 — Collector Runner Concurrency Refactor

- Registry-driven factory via slug `if/elif` — kept over importlib autoload (explicit is better, new adapters need entries anyway).
- Per-chain RPC URLs read via `os.environ` directly (not `Settings`) to avoid `DEFI_DEFI_RPC_URL_BASE` double-prefix collision.
- `shutdown_collectors()` now cancels tasks directly in addition to setting the event — fixes test-isolation issue.
- `RegistryEntry.enabled` defaults to `True` so all existing YAML entries (no field) auto-enable.
- Stub adapters (GMX, Drift, Vertex, dYdX) raise `NotImplementedError` at fetch time — caught by `_run_loop` handler, produces log noise but harmless. Use `enabled: false` to silence.

## Task 08 — Generic Opportunity Schema and API Refactor

- `LoopOpportunityOut`/`CarryOpportunityOut` made subclasses (not aliases) so existing imports stay valid.
- `strategy_details: dict` typed as `Record<string, number | null>` in TS — intentionally not a discriminated union; extensibility is the point.
- `net_apy` surfaces the headline yield (effective_yield for loop, net_carry for carry) so callers don't dig into `strategy_details`.
- `rerate_combined` unchanged — already accesses `.score`, `.rating`, `.medal` which are on `OpportunityOut`.

## Task 09 — Cross-Protocol Calculation Engine

- Single-cycle position (borrow `max_ltv * 0.9`) — recursive looping would amplify cross-protocol risk past MVP usefulness.
- Route computes on-the-fly from latest snapshots (same as loop/carry pattern) — doesn't require persisted `CrossProtocolCalculation` rows.
- Scoring: `net_spread * 10.0` — simplified; add full ranker when cross-protocol history accumulates.
- `_fetch_cross_protocol_opportunities` is O(N²) over markets per asset — fine at current scale (< 20), upgrade to JOIN query if market count grows.

## Task 10 — Historical Percentile and Rank Computation

- `get_percentile` + `get_historical_rank` are separate functions (two DB round-trips per call site). Add combined function if perf matters.
- SQL uses `PERCENT_RANK()` window function — handles ties correctly.
- Thresholds: top 5%, top 10%, top 25%, above/below median, bottom 25%.
- `window_days` inserted via string formatting (not parameterized) — safe because it's an internal int, not user input.
- Fragile pattern: mock index in `test_api.py` is positional (`mocks[6]` → `mocks[8]`); will need updating if more route queries are added.

## Task 11 — New Strategy Providers (Stable Lending, Staking, Restaking, Pendle)

- `StableLendingAdapter` returns empty list (not `NotImplementedError`) — synthetically derivable from existing snapshots when collectors write `market_type="stable_lending"`.
- `StakingAdapter` and `RestakingAdapter`: `NotImplementedError` — no stable public APIs; error messages document upgrade paths.
- `PendleAdapter`: raises `NotImplementedError` when no client injected, attempts API when client provided.
- Orchestrator: `market.market_type in _NO_BORROW_LEG_MARKET_TYPES` guard skips loop simulation — one guard in shared function vs. per-caller checks.
- `_fetch_market_type_opportunities` serves all four new types from `lending_snapshots` filtered by `market_type` — no new tables needed.

## Task 12 — Ranker and Rating Penalty Metric Updates

- Penalty detection: `k.endswith("_penalty")` added alongside existing `PENALTY_KEYS` set — `protocol_risk` stays in the set (doesn't follow naming convention).
- `_fetch_market_type_opportunities` refactored to use `score_opportunities` — staking/restaking/pendle now flow through ranker and produce `breakdown`.
- `cross_protocol_penalty` added to breakdown and `strategy_details` in cross-protocol route, computed as average risk_score of both legs.
- `bridge_penalty` in `RANKER_WEIGHTS` but no route populates it yet — ready for bridge arbitrage strategy when added.

## Task 13 — Frontend Generic Opportunity Refactor

- `kind` prop on `OpportunityCard` made optional/deprecated — not removed, to avoid breaking unknown callers.
- `STRATEGY_BADGE`/`STRATEGY_LABEL` lookup tables inlined per-component — simpler than a shared module for 3 small tables.
- Generic `strategy_details` renderer: renders all keys as `fmtPct` — safe default since all known values are rates/yields.
- 3 pre-existing `react-hooks/set-state-in-effect` lint errors untouched (pre-date this task, out of scope).
- `isCarry` / unknown strategy type guard in `opportunity-detail.tsx` — new strategy types get no charts; add dedicated branch when chart data exists for them.

## Task 14 — Integration Tests and Adapter Fixtures

- `SimpleNamespace` used for mock ORM rows — `SQLAlchemy.__new__()` skips `_sa_instance_state` injection and raises `AttributeError`.
- `session.add.side_effect` injects `.id` onto `Protocol`/`Market` objects at add-time — necessary because collectors read back `.id` after `flush()`.
- No staking/pendle fixture JSON files — adapters return empty or raise at import, not at `fetch_reserves()`. Inline dicts used in tests (same as existing pattern).
- No new conftest fixtures added — existing `mock_db_session_factory` sufficient; adding would risk breaking 301 existing tests.
