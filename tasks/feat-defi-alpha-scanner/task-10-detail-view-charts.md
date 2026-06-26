# Task 10: Opportunity Detail View + Historical Charts + Deep Link

## Objective
Build the detail view that opens when an opportunity is selected: full metrics, historical Yield / Borrow / Spread charts (recharts), and an "Open in <protocol> →" deep link when known (PRD #9).

## Context
**Quick Context:**
- Opened from the feed (task-09) and terminal hero (task-08) via the `onOpenDetail(opp)` contract. Rendered as an overlay/panel.
- Charts pull from the existing `/history` endpoint (`getHistory`) which already serves lending (deposit_apy, borrow_apy) and funding (funding_rate, annualized_funding) time-series by `market_id`. Spread = derived series (deposit_apy − borrow_apy) computed client-side from the two lending series.
- **This task owns `funding-chart.tsx`**: reuse its recharts `LineChart` setup for the detail charts (extract into a small reusable chart, or adapt in place), then delete `funding-chart.tsx` if fully superseded.

## ⚠️ MANDATORY FRONTEND PRE-READ
Before writing ANY frontend code: if `frontend/node_modules` is absent run `npm install` (in `frontend/`), then read `frontend/AGENTS.md` and the bundled docs in `frontend/node_modules/next/dist/docs/`. This is a modified Next.js 16 with breaking changes vs. training data — code written from memory will be wrong.

## Requirements
- New `frontend/src/components/opportunity-detail.tsx` (client component) taking the selected opportunity + an `onClose` handler:
  - Header: protocol / asset, and the full metric set (deposit/borrow/net/effective, TVL, liquidity, risk label).
  - **Historical charts (recharts)**: Historical Yield, Historical Borrow, Historical Spread. Fetch via `getHistory({ type, market_id, field })`. Spread = client-side diff of deposit_apy and borrow_apy series (align by `observed_at`).
  - **Deep link**: `protocolLink(opp.protocol)` from task-05 — render "Open in <protocol> →" only when non-null; hide otherwise.
  - Loading/error/empty states per chart.
- The opportunity object carries `market_id` for history queries — task-04 adds it to the response + `api.ts` types. Consume it; do NOT modify the backend or `api.ts` here.
- Reusable chart: factor the recharts LineChart from `funding-chart.tsx` into a small `<HistoryChart points={...} label={...} />` (new file or inside this component). Delete `funding-chart.tsx` once nothing imports it.

## Existing Code References
- `frontend/src/components/funding-chart.tsx` — recharts `LineChart` pattern to reuse (THIS TASK OWNS IT).
- `frontend/src/lib/api.ts` — `getHistory`, `HistoryPointOut`; opportunity types.
- `frontend/src/lib/protocol-links.ts` — `protocolLink` (task-05).
- `backend/app/api/routes.py:get_history` — supported `type`/`field` values (funding: funding_rate/annualized_funding; lending: deposit_apy/borrow_apy).

## Implementation Details
- Spread series: zip the deposit_apy and borrow_apy history by matching `observed_at`; value = deposit − borrow. Skip unmatched timestamps.
- `market_id` is provided by task-04; this task is frontend-only.

## Acceptance Criteria
- [ ] Detail view opens with full metrics for the selected opportunity and closes via `onClose`
- [ ] Three recharts line charts render: Yield, Borrow, Spread (spread derived client-side)
- [ ] "Open in <protocol> →" shows only for protocols in the link map
- [ ] Detail view uses `opp.market_id` (provided by task-04) for history queries
- [ ] `funding-chart.tsx` reused then removed if superseded; no dangling import
- [ ] `npm run build` succeeds (in `frontend/`)

## Dependencies
- Depends on: 04, 05, 07
- Blocks: 09
