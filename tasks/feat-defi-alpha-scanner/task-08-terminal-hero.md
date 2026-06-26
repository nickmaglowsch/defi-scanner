# Task 08: Terminal-Style "Today's Best Opportunities" Hero

## Objective
Build the terminal-style hero board that headlines the landing page — a compact, monospace "Today's Best Opportunities" list with status dots, rating labels, and short-lived/avoid flags (PRD #10).

## Context
**Quick Context:**
- The landing experience: a Bloomberg-terminal-feeling board listing the top opportunities, with everything else as supporting detail below. The unified feed (task-09) renders this hero at the top of `page.tsx`.
- Consumes `getOpportunities` (top N by rating) and shares the `opportunity-card` expandable detail only on click — the hero rows themselves are a denser, terminal-styled list, not full cards.

## ⚠️ MANDATORY FRONTEND PRE-READ
Before writing ANY frontend code: if `frontend/node_modules` is absent run `npm install` (in `frontend/`), then read `frontend/AGENTS.md` and the bundled docs in `frontend/node_modules/next/dist/docs/`. This is a modified Next.js 16 with breaking changes vs. training data — code written from memory will be wrong.

## Requirements
- New `frontend/src/components/terminal-hero.tsx` (client component):
  - Fetch top opportunities via `getOpportunities({ sort: "return", limit: N })` (N≈6-8).
  - Render each as a dense terminal row: `🟢 Loop USDC 11.3% Excellent` / `🟡 Funding Spike ETH 24% Short-lived` / `🔴 LP Avoid` — status dot from risk/rating, strategy + asset + yield + rating_label.
  - Monospace font, dark "terminal" aesthetic via Tailwind (e.g. `font-mono`, dark bg, subtle green accents). Keep it tasteful — readable, not a gimmick.
  - "Short-lived" tag when a carry/funding opportunity has high volatility / low confidence (use `confidence` and/or sharpe as the heuristic); "Avoid" when `rating_label === "Avoid"`.
  - Clicking a row opens the detail view (task-10) — call an `onOpenDetail(opp)` prop or shared handler; define the contract, don't hard-wire navigation.
- Loading / error / empty states (mirror the old components' simple states).

## Existing Code References
- `frontend/src/lib/api.ts` — `getOpportunities`, extended opportunity types (task-04).
- `frontend/src/components/funding-chart.tsx`, `loop-table.tsx` — loading/error/empty state patterns.
- `frontend/src/components/opportunity-card.tsx` (task-07) — for the risk-color / ⭐ helpers; reuse or mirror, don't duplicate the whole card.

## Implementation Details
- The hero is denser than the card — reuse the small risk-color/label helpers from task-07 (import them if task-07 exports them; otherwise mirror the tiny logic) rather than rendering full cards.
- Keep the terminal styling in this file via Tailwind classes; no new dependency.

## Acceptance Criteria
- [ ] Hero fetches and lists top N opportunities as dense terminal rows with status dot + strategy + asset + yield + rating label
- [ ] "Short-lived" / "Avoid" flags appear per the documented heuristic
- [ ] Monospace terminal aesthetic; loading/error/empty states handled
- [ ] Clicking a row triggers the detail-open contract
- [ ] `npm run build` succeeds (in `frontend/`)

## Dependencies
- Depends on: 04, 07
- Blocks: 09
