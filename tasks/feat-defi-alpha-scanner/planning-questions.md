# Planning Questions

## Codebase Summary

Verified the recon — it's accurate. Concrete findings that shape the plan:

**Backend (FastAPI + SQLAlchemy async + Postgres + pytest)**
- `app/calculations/ranker.py:score_opportunities()` computes the 7 component scores, min-max normalizes them, weighted-sums into `score`, sorts, ranks — then **discards the normalized components** (only `score` and `rank` survive on the dict, lines 50-67). Exposing the breakdown (PRD #5) means returning the per-component normalized values + weights, which requires plumbing them out of the ranker.
- `app/api/routes.py` `/opportunities` is already the unified loop+carry endpoint with filters; loop & carry calcs are pure (`looping.py`, `carry.py`) and cached in `LoopCalculation`/`CarryCalculation` tables.
- `Protocol` model has `id, name, type, chain, risk_score, created_at`. **No protocol-age, audit-history, or deep-link/URL fields exist.** `created_at` is row-insert time (when our seeder ran), not protocol launch date — useless as a real age proxy.
- History data exists in `lending_snapshots` (deposit_apy, borrow_apy) and `funding_snapshots` (funding_rate, annualized_funding), indexed by market_id + observed_at. There is **no stored history of computed `effective_yield` / `net_carry` / `spread`** — those are derived per-request. So "Today / Yesterday / 7D / 30D of yield" (PRD #4) must be recomputed from raw APY history, OR approximated from the raw input fields' history.
- No returns time-series exists anywhere (Sharpe has no natural input).
- Tests: pytest + pytest-asyncio, `backend/tests/conftest.py` fixtures, files `test_api/looping/carry/ranker/alerts/*_adapter`.

**Frontend (Next.js 16, React 19, Tailwind v4, shadcn)**
- `frontend/AGENTS.md` warns: **this is a modified Next.js with breaking changes vs. training data — read `node_modules/next/dist/docs/` before writing frontend code.** (Note: `node_modules` isn't installed in this checkout yet, so that doc-read must happen at implementation time after `npm install`.)
- Installed: recharts, @tanstack/react-table, lucide-react, @base-ui/react, shadcn ui primitives (Button/Card/Input/Select/Table). **No react-query** — components use `useState/useEffect + fetch` via `src/lib/api.ts`.
- `page.tsx` = title + home-cards + loop-table + carry-table + funding-chart.
- Minor drift to fix in passing: `api.ts:FundingSnapshotOut` is missing the `asset`/`protocol` fields the backend now returns.

---

## Questions

### Q1: Rating Engine math — confidence formula and label thresholds (with partly-synthetic inputs)
**Context:** The killer Rating Engine needs a 0-100 score, a confidence %, and a label (Excellent / Very Good / etc.), layered over the existing 7 component scores. The user already accepted that protocol-age, audit-history, and persistence inputs are stubbed/heuristic for now. But the *shape* of the formulas is a real decision that the engine and all the UI labels depend on.
**Question:** For the first build, confirm these defaults (I'll use them unless you say otherwise):
- **Score 0-100** = the existing weighted ranker `score`, but min-max normalized across the batch ×100 (so the top opportunity is ~100). Acceptable, or do you want an absolute scale (e.g. fixed yield/risk bands) so a weak day doesn't show a "100"?
- **Label thresholds** on that 0-100: Excellent ≥85, Very Good ≥70, Good ≥55, Fair ≥40, Avoid <40.
- **Confidence %** = a function of *data completeness + sample depth*: starts at a base, penalized when an input is stubbed (age/audit/persistence) and when snapshot history is thin (< N points). So stubbed-heavy opportunities visibly read lower confidence. Good approach, or do you have a specific confidence definition in mind?

### Q2: Sharpe sort with no returns series
**Context:** PRD #6 lists "Sharpe" as a sort option, but there is no returns time-series in the DB — only raw APY/funding snapshot history. A true Sharpe ratio isn't computable.
**Question:** Which do you want?
- A) **Approximate Sharpe** = expected net yield ÷ APY volatility (we already compute a volatility penalty via STDDEV of recent funding rates / we can do the same for deposit_apy). Cheap, directionally meaningful, clearly labeled as an approximation.
- B) **Drop "Sharpe"** from the sort list for now and ship Expected Return / Risk / Confidence / Liquidity; add Sharpe when a real returns series exists.
- C) Something else.
(I lean A — it reuses existing volatility infra and keeps the PRD's sort option.)

### Q3: Capital Simulator — default value and persistence
**Context:** PRD #7 wants a global capital input (e.g. $20,000) that converts every yield to $/yr and $/mo across all cards. This is global UI state with no backend involvement.
**Question:** Confirm: default **$20,000**, persisted in **localStorage** (survives reload, no backend, no auth), shared via a React context provider at the app root. Is localStorage fine, or do you want it purely in-memory (resets each load)? And is $20,000 the right default?

### Q4: Fate of the old tables / page — delete vs. keep behind a route
**Context:** PRD #1/#6 replace the two static tables with a unified feed; PRD #10 wants a terminal-style "Today's Best Opportunities" board as the new landing. The existing `page.tsx`, `loop-table.tsx`, `carry-table.tsx`, `funding-chart.tsx` would be superseded.
**Question:** When the new feed + terminal landing ship, should I **delete** `loop-table.tsx` / `carry-table.tsx` and rebuild `page.tsx`, or **keep the old tables behind a secondary route** (e.g. `/classic`) during transition? (Deleting is cleaner and these are easily recovered from git; I'll delete unless you want the fallback route.)

### Q5: "Open in protocol" deep links when no URL exists
**Context:** PRD #9 wants an "Open in Morpho →" link on the detail view, but there is no URL field on `Protocol` or `Market` anywhere in the schema.
**Question:** How should deep links work for the first build?
- A) **Static hardcoded map** of protocol name → base app URL (e.g. Aave → app.aave.com), shown only when a protocol is in the map; hidden otherwise. No schema change, no new collector. (Lazy default — fits the "defer new data collection" constraint.)
- B) Add a nullable `url` column to `Protocol` and seed it manually.
- C) Skip deep links entirely for now.
(I lean A.)

### Q6: TDD mode
**Context:** Standing question for every build. The backend has a solid pytest suite (ranker/looping/carry/api all covered); the Rating Engine is pure-function-shaped and naturally testable. Frontend has no test setup today.
**Question:** Do you want **TDD mode** for this build? If yes, the task implementer writes failing tests before implementation code for each task (I'll scope it to the backend pure functions + API where it pays off, since there's no frontend test harness yet — say if you want a frontend test harness stood up too).
