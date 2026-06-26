# Task 07: Shared Opportunity Card Component

## Objective
Build the reusable, risk-first opportunity card that every feed/leaderboard/hero entry renders: headline yield, risk label, ⭐/100 score + rating label, $/yr & $/mo from the capital simulator, loop health, and an expandable "WHY" breakdown + history (PRD #2, #3, #4, #5, #7, #8).

## Context
**Quick Context:**
- This is the heaviest shared frontend surface — the feed (task-09), terminal hero (task-08), and leaderboard (task-11) all render this card. It owns ONE file (`opportunity-card.tsx`) so those tasks don't collide.
- Consumes the new API fields from task-04 (rating, rating_label, confidence, medal, sharpe, breakdown, weights, history) and the capital context + `yieldToDollars` from task-06.

## ⚠️ MANDATORY FRONTEND PRE-READ
Before writing ANY frontend code: if `frontend/node_modules` is absent run `npm install` (in `frontend/`), then read `frontend/AGENTS.md` and the bundled docs in `frontend/node_modules/next/dist/docs/`. This is a modified Next.js 16 with breaking changes vs. training data — code written from memory will be wrong.

## Requirements
- New `frontend/src/components/opportunity-card.tsx` (client component) taking a `LoopOpportunityOut | CarryOpportunityOut` (discriminated by which fields are present, or add a `kind` prop the caller sets).
- **Headline (risk-first, PRD #2)**: strategy label (e.g. "Loop / Morpho / USDC"), net/effective yield %, risk label with color dot (🟢 Low / 🟡 Medium / 🔴 High derived from `risk_score`/`rating_label`), liquidity, TVL.
- **Score (PRD #5)**: ⭐ rendering of `rating`/100 (e.g. ⭐⭐⭐⭐☆) + `rating_label` text + `confidence`%.
- **Capital conversion (PRD #7)**: read `useCapital()`, show "Expected Return X% ≈ $Y/year (≈ $Z/month)" via `yieldToDollars`.
- **Loop health (PRD #8)**, only for loop opps: Current LTV / Liquidation / Distance (from leverage/safety_margin/liquidation_distance already on `LoopOpportunityOut`) with a health emoji (🟢/🟡/🔴 from `safety_margin`/`liquidation_distance`).
- **Expandable "WHY" (PRD #3)**: a toggle that reveals the component breakdown using `breakdown` + `weights` (e.g. "Yield 40% / Liquidity 25% / …" with the normalized contribution), and the loop/carry math (deposit/borrow/target LTV/loops → net; funding/borrow/fees → carry) from the fields already on the response.
- **History (PRD #4)**: show Today / Yesterday / 7D Avg / 30D Avg of yield from `history`; render "—" when a bucket is null.
- **Sharpe**: when present, show with an "approx" qualifier; hide when null.
- Use shadcn `Card`/`Button` + lucide icons; Tailwind v4. Handle null fields gracefully (mirror the `fmtPct` pattern from the old loop-table).

## Existing Code References
- `frontend/src/components/loop-table.tsx` — `fmtPct` null-formatting pattern; the fields available on `LoopOpportunityOut`.
- `frontend/src/lib/api.ts` — `LoopOpportunityOut`/`CarryOpportunityOut` (extended in task-04).
- `frontend/src/lib/capital-context.tsx` — `useCapital`, `yieldToDollars` (task-06).
- `frontend/src/components/ui/card.tsx`, `ui/button.tsx`.

## Implementation Details
- Keep the card a presentational component driven by props + the capital hook; data fetching lives in the feed/hero, not here.
- Clicking the card body (or a "Details" affordance) should call an `onOpenDetail?` prop so task-10's detail view can open — define the prop, don't implement navigation here.
- Derive risk color and ⭐ count with small pure helpers in this file.

## Acceptance Criteria
- [ ] Card renders strategy label, yield %, risk label+color, liquidity, TVL
- [ ] ⭐/100 + rating label + confidence% shown
- [ ] $/year and $/month shown and update live when capital changes
- [ ] Loop cards show LTV / liquidation / distance + health emoji; carry cards omit loop-health block
- [ ] Expand toggle reveals component-weight breakdown + the loop/carry math
- [ ] Today/Yesterday/7D/30D history shown, "—" for null buckets
- [ ] Sharpe shown with "approx" when present, hidden when null
- [ ] `npm run build` succeeds (in `frontend/`)

## Dependencies
- Depends on: 04, 06
- Blocks: 08, 09, 11
