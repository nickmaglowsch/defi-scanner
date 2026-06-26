# Task 09: Unified Opportunity Feed / Screener + Rebuilt Landing Page

## Objective
Replace the two static tables with a single "All Opportunities" feed/screener: type filter (Loop / Carry / …), Sort by (Expected Return / Risk / Confidence / Sharpe / Liquidity), rendering opportunity cards; and rebuild `page.tsx` as terminal hero + feed (PRD #1, #6). Delete the old tables.

## Context
**Quick Context:**
- This task owns the landing page composition (`page.tsx`) and the new feed component, and performs the DELETION of `loop-table.tsx` / `carry-table.tsx` (and `funding-chart.tsx` unless task-10 reuses it).
- Composes: terminal hero (task-08) on top, then the screener (filters + sorted list of `opportunity-card`s from task-07). Capital input (task-06) lives in the top-right of the page header.

## ⚠️ MANDATORY FRONTEND PRE-READ
Before writing ANY frontend code: if `frontend/node_modules` is absent run `npm install` (in `frontend/`), then read `frontend/AGENTS.md` and the bundled docs in `frontend/node_modules/next/dist/docs/`. This is a modified Next.js 16 with breaking changes vs. training data — code written from memory will be wrong. **Confirm the App Router page/component conventions from the bundled docs before rebuilding `page.tsx`.**

## Requirements
- New `frontend/src/components/opportunity-feed.tsx` (client component):
  - Filters: Type (all / loop / carry — use shadcn `Select`, reuse the asset/protocol filter pattern from the old `loop-table.tsx`), plus asset/protocol filters.
  - Sort by: Expected Return / Risk / Confidence / Sharpe (labeled "approx") / Liquidity → maps to the `sort` query param added in task-04 (`return`/`risk`/`confidence`/`sharpe`/`liquidity`).
  - Fetch via `getOpportunities({ type, asset, protocol, sort, limit })`; render each result as an `opportunity-card` (task-07).
  - Loading/error/empty states.
  - Wire each card's `onOpenDetail` to open the detail view (task-10).
- Rebuild `frontend/src/app/page.tsx`:
  - Header with title + the capital input (task-06) top-right.
  - `<TerminalHero />` (task-08), `<RatingLeaderboard />` (task-11), then `<OpportunityFeed />`.
  - Remove the old Loop/Carry table sections.
- **Delete** `frontend/src/components/loop-table.tsx` and `frontend/src/components/carry-table.tsx`. Do NOT touch `funding-chart.tsx` — task-10 owns that file (it decides reuse-vs-delete for the detail charts). Just stop importing it in `page.tsx`.

## Existing Code References
- `frontend/src/app/page.tsx` — current composition to replace.
- `frontend/src/components/loop-table.tsx` — filter-bar + Select + loading/error/empty patterns to reuse.
- `frontend/src/components/opportunity-card.tsx` (task-07), `terminal-hero.tsx` (task-08), `rating-leaderboard.tsx` (task-11), `capital-input.tsx` (task-06), `opportunity-detail.tsx` (task-10).
- `frontend/src/lib/api.ts` — `getOpportunities` + `OppParams.sort` (task-04).

## Implementation Details
- Keep data fetching in the feed component (`useState/useEffect + fetch` via the api client) — match the existing pattern, no react-query.
- Detail opening: hold the selected opportunity in state at the page (or feed) level and render task-10's detail view as an overlay/panel; define the open/close handlers here and pass down.

## Acceptance Criteria
- [ ] Single feed lists loop + carry opportunities as cards with Type + asset + protocol filters
- [ ] Sort by Expected Return / Risk / Confidence / Sharpe / Liquidity works (hits the `sort` param)
- [ ] `page.tsx` shows header + capital input + terminal hero + feed; old table sections gone
- [ ] `loop-table.tsx` and `carry-table.tsx` deleted
- [ ] Selecting a card/row opens the detail view
- [ ] `npm run build` succeeds (in `frontend/`)

## Dependencies
- Depends on: 04, 06, 07, 08, 10, 11
- Blocks: None
