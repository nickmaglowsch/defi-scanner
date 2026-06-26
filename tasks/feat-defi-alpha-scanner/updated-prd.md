# Updated PRD — DeFi Alpha Scanner: Decision Engine

The product currently looks like DefiLlama (a data explorer). It must become Bloomberg + TradingView — a **decision-making tool**. This PRD grounds the original 10 sections + the killer Rating Engine in the actual codebase.

## What already exists (do NOT rebuild)
- **Unified opportunity backend**: `GET /api/v1/opportunities` already merges loop + carry with filters (type, asset, protocol, min_yield, min_liquidity, limit) and sorts by score. `/looping`, `/funding`, `/history`, `/protocols`, `/assets` exist.
- **Component scoring**: `ranker.py:score_opportunities()` already computes 7 component scores (yield, liquidity, tvl, stability, utilization_penalty, volatility_penalty, protocol_risk), min-max normalizes, weighted-sums, ranks. **It discards the normalized components** — only `score`/`rank` survive (~lines 50-67). PRD #5 needs them plumbed OUT, not recomputed.
- **Calc engines**: `simulate_looping()` (effective_yield, leverage, safety_margin, liquidation_distance, risk_score) and `calculate_carry()` (net_carry, risk_score) are pure functions, results cached in `LoopCalculation`/`CarryCalculation`.
- **History data**: `lending_snapshots` (deposit_apy, borrow_apy, utilization, tvl, available_liquidity) and `funding_snapshots` (funding_rate, annualized_funding, open_interest, volume_24h) are time-series indexed by `market_id + observed_at`. Used today by `/history` for funding/lending fields.
- **Volatility infra**: `routes.py:_volatility_map()` computes windowed STDDEV of funding_rate per market (window = `DEFI_VOLATILITY_WINDOW`, default 20). Reusable for Sharpe + confidence.
- **Frontend**: recharts, @tanstack/react-table, lucide-react, shadcn UI all installed; `src/lib/api.ts` typed client; `funding-chart.tsx` recharts LineChart pattern.

## Constraints accepted by the user (stubbed / deferred data)
Protocol **age**, **audit history**, and opportunity **persistence** are NOT collected today and **no new collectors will be built** for them now.
- `Protocol.created_at` is row-insert time (when our seeder ran), **NOT** protocol launch date — must not be used as a real age proxy.
- Use a **static stubbed protocols-metadata source** (a Python map keyed by protocol name) for age + audit fields.
- Persistence/volatility are derived from existing snapshot history where possible.
- Rating **confidence** is therefore partly synthetic until those data sources exist. This is accepted and must be surfaced honestly: stubbed-heavy opportunities read **lower confidence**.

## Decisions locked for this build

### Rating Engine (killer feature) — exact formulas
Layered over the existing ranker output. For a batch of scored opportunities:

- **Score 0-100 (RELATIVE)**: `rating = (raw_score - min_raw_score) / (max_raw_score - min_raw_score) * 100` across the current batch, so the top opportunity ≈ 100. If the batch range is 0 (all equal), all get 100. This is intentionally relative — a weak day can still show a 100; documented so the UI is deterministic.
- **Label thresholds** on `rating`:
  - Excellent ≥ 85
  - Very Good ≥ 70
  - Good ≥ 55
  - Fair ≥ 40
  - Avoid < 40
- **Confidence % (0-100)** = `base × completeness_factor × depth_factor`, clamped to [0, 100]:
  - `base = 100`
  - `completeness_factor`: start at 1.0; subtract **0.15 for each stubbed input** used (protocol age, audit history, persistence) → min floor 0.4. (3 stubbed inputs → 1.0 − 0.45 = 0.55.)
  - `depth_factor`: based on number of historical snapshot points `n` available for the opportunity's market. `depth_factor = min(1.0, n / N)` where `N = DEFI_VOLATILITY_WINDOW` (20). Thin history (e.g. n=4) → 0.2 factor.
  - Result: a fresh opportunity with all 3 stubbed inputs and thin history reads visibly low confidence (e.g. 0.55 × 0.2 × 100 ≈ 11%); a mature, well-populated one approaches the completeness ceiling (~55% when all 3 inputs remain stubbed). When real age/audit/persistence data arrives, drop the corresponding completeness penalty.
- **Leaderboard**: opportunities sorted by `rating` desc; top 3 get 🥇🥈🥉 medals. Output row = {rank/medal, strategy label, expected_return, risk_label, confidence}.

### Sharpe (APPROXIMATE)
`sharpe ≈ expected_net_yield / apy_volatility`, where apy_volatility = STDDEV of recent values (deposit_apy for loops, funding_rate for carry) over the volatility window. When volatility is 0/unknown, omit Sharpe (null) rather than divide by zero. UI labels it **"approx"**. Kept as a sort option.

### Capital Simulator
Global capital value, default **$20,000**, persisted in **localStorage**, exposed via a React context provider at the app root. Every opportunity card converts its expected return %: `$ / year = capital × return%/100`, `$ / month = that / 12`.

### Old tables: DELETE & REBUILD
Remove `loop-table.tsx` and `carry-table.tsx`; rebuild `page.tsx` around the new unified feed + terminal-style "Today's Best Opportunities" hero. `funding-chart.tsx` LineChart logic may be reused inside the detail view; otherwise delete. No `/classic` fallback route.

### Deep links
Static hardcoded protocol-name → app-URL map. Show "Open in <protocol> →" only when the protocol is in the map; hide otherwise. No schema change, no new collector.

### TDD: BACKEND ONLY
Backend tasks (Rating Engine, score-breakdown plumbing, history aggregation, schema/API changes) use TDD (RED → GREEN → REFACTOR) with pytest. Frontend tasks have no tests (no harness exists; not standing one up).

## Feature mapping (PRD section → task)
- #1 Opportunity Feed → task-09 (feed/screener page)
- #2 Risk first-class → task-07 (opportunity card) + task-04 (rating/risk labels backend)
- #3 Explain WHY (breakdown) → task-01 (expose component breakdown) + task-07 (card expandable)
- #4 History today/yesterday/7D/30D → task-02 (backend aggregation) + task-07/task-10 (display)
- #5 Opportunity Score ⭐/100 + weights → task-01 (breakdown) + task-04 (rating) + task-07 (display)
- #6 Unified screener + sort → task-04 (Sharpe/rating in API + sort) + task-09 (page)
- #7 Capital Simulator → task-06 (context) + task-07 (card conversion)
- #8 Health Score (loops) → task-07 (card; data already in LoopOpportunityOut)
- #9 Opportunity Details + charts + deep link → task-10
- #10 Terminal hero "Today's Best" → task-08
- Killer Rating Engine + leaderboard → task-03 (engine) + task-04 (wire to API) + task-11 (leaderboard UI)

## Open Questions
_None blocking — all planning questions answered. Items below are non-blocking notes for the implementer / reviewer:_
- The relative 0-100 rating means "Excellent" is always achievable even on a poor day. Accepted per Q1 (RELATIVE). If an absolute scale is later desired, only `task-03`'s normalization changes.
- Sharpe is null when volatility is unavailable; the feed's Sharpe sort will push null-Sharpe rows to the bottom. Acceptable for v1.
