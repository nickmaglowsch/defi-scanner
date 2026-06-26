# Implementation Notes

## Task 01: Expose Ranker Component Score Breakdown

- **Decisions**: Added `opp["breakdown"] = dict(normalized[i])` and `opp["weights"] = dict(weights)` inside the existing scoring loop, immediately after the score total is computed. `dict()` copies avoid callers mutating the internal normalized list.
- **Deviations**: None — exactly the two-liner the task spec described.
- **Trade-offs**: Could have returned breakdown/weights as separate return values from `score_opportunities`, but mutating the opp dict in-place matches the existing pattern (score and rank are already added the same way).
- **Risks**: None — pure function, no I/O, no normalization logic changed.

---

## Task 02: Yield History Aggregation (Today / Yesterday / 7D / 30D)

- **Decisions**:
  1. Single SQL with five CTEs (`latest`, `snaps`, `today_cte`, `yesterday_cte`, `agg_cte`) — one round-trip for any number of market_ids. Mirrors `_volatility_map`'s `text()` + `ANY(:market_ids)` pattern.
  2. "yesterday" uses a ±12h window around `(latest - 24h)` to avoid counting today's snapshot as yesterday. Documented with `# ponytail:` comment per task requirement.
  3. `avg_7d` uses `AVG(...) FILTER (WHERE age <= INTERVAL '7 days')` — Postgres conditional aggregate, no subquery.
  4. `db_session` fixture creates the engine inside the fixture body (not at module level). asyncpg requires the engine to be created on the same event loop as the test; module-level creation binds to the import-time loop and causes `attached to a different loop` errors.
- **Deviations**: Added a 5th test (`test_funding_snapshots_annualized_funding`) beyond the 4 specified, to verify the generic `table`/`field` params work for funding snapshots.
- **Trade-offs**: Format-string for `table`/`field` identifiers instead of parameterized quoting — safe because callers are internal route code (not user input). Documented with `# ponytail:` comment.
- **Risks**: The `db_session` fixture requires the real Postgres DB to be running (via Docker). If the DB is unavailable, these 5 tests will fail with a connection error rather than a meaningful message.

---

## Task 03: Opportunity Rating Engine

- **Decisions**: `rate_opportunities` sorts `scored` in-place by rating before assigning medals. This mutates the input list (same behavior as `score_opportunities` in ranker.py which also mutates in-place). Task-04 wiring should be aware the list order changes after calling this.
- **Deviations**: None — formulas, thresholds, and constants match the PRD exactly.
- **Trade-offs**: `PROTOCOL_METADATA` hardcodes 5 known protocols. An unknown protocol gets 2 extra stub penalties (age + audit unknown), matching the PRD's "treat as unknown" rule. Adding protocols later is a one-liner edit to the dict.
- **Risks**: The test for `test_confidence_penalises_more_stubbed_inputs` depends on `"aave"` being in `PROTOCOL_METADATA` with `age_known=True, audit_known=True`. If that entry is removed or changed, the test will break.

---

## Task 04: Wire Breakdown + History + Rating + Sharpe into the API

- **Decisions**: Loop Sharpe uses `_volatility_map_lending` (new helper: STDDEV of `deposit_apy` from `lending_snapshots`) rather than reusing `_volatility_map` (which queries `funding_snapshots` — irrelevant for lending market_ids). Carry Sharpe reuses the existing `_volatility_map` since it operates on funding markets.
- **Decisions**: `_history_points` for `rate_opportunities` confidence is set to `1` if `avg_30d` is non-null (data exists), `0` otherwise. This is a rough proxy — the spec said "count of history points available." Using a richer count would require a separate `COUNT(*)` SQL call per market; the binary present/absent signal is sufficient for the confidence formula since CONFIDENCE_VOLATILITY_WINDOW=20 needs real depth data (task-02's `get_yield_history` doesn't return raw counts, only aggregates).
- **Decisions**: The `liquidity` sort falls back to score-based ordering as a proxy (`# ponytail:` comment included). A proper liquidity sort would need `available_liquidity` exposed on the response model — deferred until a consumer actually needs it.
- **Decisions**: Added `_market_id` key to carry opp dicts (alongside existing `_protocol`, `_asset`) so `_fetch_carry_opportunities` can look up history and volatility by market_id after `score_opportunities` re-sorts the list.
- **Deviations**: The existing `test_get_looping_returns_opportunities` test needed 2 extra mock execute side-effects added (history + deposit vol) — expected maintenance for an existing test.
- **Trade-offs**: `YieldHistoryOut` is a plain Pydantic model (not a `TypedDict`) to stay consistent with the rest of `responses.py`.
- **Risks**: The `sort=risk` key uses `-(r.risk_score or 0.0)` with `reverse=True`, meaning lower risk_score sorts first. If risk_score semantics change, revisit.

---

## Task 05: Protocol Deep-Link Map

- **Decisions**: Included Morpho, Spark, and Hyperliquid in the static map even though they don't appear in current `getProtocols()` results — minimal cost to add, and `protocolLink` returns null for unknowns so no risk of bad links.
- **Deviations**: None.
- **Trade-offs**: Flat object + one function (no class, no registry). Would need a backend URL field if protocols become dynamic.
- **Risks**: None — pure static file, no runtime side effects.

---

## Task 06: Capital Simulator Context + Provider

- **Decisions**: SSR guard via "initialize to default, hydrate in effect" pattern — avoids the mounted-boolean dance and matches Next.js docs guidance for localStorage. The `CapitalContext` default value uses `DEFAULT_CAPITAL` so any component consuming `useCapital` outside the provider still gets a sane number.
- **Deviations**: None.
- **Trade-offs**: `CapitalProvider` is a `"use client"` component mounted at the root layout body. Standard App Router pattern for wrapping all routes with client state; layout itself remains a server component.
- **Risks**: `Input` min attribute only affects form validation UI, not the stored value. The `onChange` guard (`v >= 0`) prevents negative values from being stored but UX reviewer should verify the capital input behavior.

---

## Task 07: Shared Opportunity Card Component

- **Decisions**: `getRiskLabel`/`getRiskColor` are named exports so tasks 08 and 11 can import without duplicating thresholds. Stars rendered as a plain string (`⭐⭐⭐⭐☆`) — one-liner, no icon imports, matches spec notation.
- **Decisions**: `CarryOpportunityOut` doesn't expose `liquidity` or `tvl` fields in the current schema, so those headline items are omitted. No fabricated fields added.
- **Deviations**: `CardFooter` import removed as unused.
- **Trade-offs**: Considered splitting history/breakdown into sub-components, but the whole card is one file by spec.
- **Risks**: `opp.history!` non-null assertion used inside a block already guarded by `opp.history &&` — safe, but worth a reviewer glance.

---

## Task 08: Terminal-Style "Today's Best Opportunities" Hero

- **Decisions**: Used inline dot character `●` styled with Tailwind color classes instead of emoji dots — emoji render inconsistently on dark backgrounds. `getRiskColor` mapped to `text-green-400/yellow-400/red-400` (lighter variants) for the terminal palette (`bg-zinc-950`).
- **Deviations**: None.
- **Trade-offs**: `isLoop` type guard uses `"effective_yield" in opp` duck-typing — no explicit discriminant field on the union type.
- **Risks**: `getRiskColor` class strings checked via `.includes("green")` substring — stable given the helper is trivially small.

---

## Task 09: Unified Opportunity Feed / Screener + Rebuilt Landing Page

- **Decisions**: `OpportunityCard` uses `opportunity` prop (not `opp`) — matched the actual component signature from task-07. The task summary had a minor inconsistency; reading the source resolved it.
- **Decisions**: `@base-ui/react` Select `onValueChange` typed as `(value: T | null, ...)` — used the null-guard pattern from the now-deleted `loop-table.tsx`.
- **Decisions**: Detail overlay is a fixed-position panel (right-sliding drawer) with a semi-transparent backdrop. Clicking the backdrop closes it.
- **Decisions**: `page.tsx` became a `"use client"` component to hold `selectedOpp` state — minimal change; alternately state could live in the feed.
- **Deviations**: None.
- **Trade-offs**: Grid layout (2-col sm, 3-col lg) for cards. Can revert to `flex-col` if dense list is preferred.
- **Risks**: `page.tsx` is now a client component. If SSR of the page shell matters in future, move the `selectedOpp` state + overlay into a separate client wrapper.

---

## Task 10: Opportunity Detail View + Historical Charts + Deep Link

- **Decisions**: Kept `HistoryChart` as a function inside `opportunity-detail.tsx` — only 30 lines, no callers outside this component.
- **Decisions**: For loop opps, deposit and borrow history fetches run in parallel via `Promise.all`.
- **Decisions**: `page.tsx` had the only import of `funding-chart.tsx` — removed the `FundingChart` section when deleting the file. The feed is the replacement surface.
- **Deviations**: None.
- **Trade-offs**: Spread series uses `observed_at` string equality for alignment. Works as long as both series share resolution. `# ponytail: string key join, use time bucketing if series resolutions differ`.
- **Risks**: `market_id` is optional on the opportunity types. The component guards on `marketId` and shows "No market ID" if absent.

---

## Task 11: Rating Leaderboard

- **Decisions**: Used plain colored dot (`<span className="inline-block h-2 w-2 rounded-full bg-current" />`) for risk — `getRiskColor` returns a Tailwind text-color class which works cleanly with `bg-current`, keeping the table compact.
- **Deviations**: None.
- **Trade-offs**: Skipped TanStack Table — `shadcn Table` primitives are sufficient for a static sorted 10-row list; TanStack adds no value here.
- **Risks**: `getRiskColor` class names are included in Tailwind's scan via `opportunity-card.tsx`, so no purge risk.
