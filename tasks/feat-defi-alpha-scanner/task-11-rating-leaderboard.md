# Task 11: Rating Leaderboard

## Objective
Render the killer-feature leaderboard: a ranked 🥇🥈🥉 table answering "If I had $20,000 to deploy today, where should it go?" — Rank / Strategy / Expected Return / Risk / Confidence.

## Context
**Quick Context:**
- The Rating Engine (task-03) already produces `rating`, `medal`, `confidence`, `rating_label` per opportunity via the API (task-04). This is a presentational ranked table on top of `getOpportunities`.
- Lives on the landing page (rendered by task-09's `page.tsx`) or as its own section; uses the capital context (task-06) to show expected $ alongside %.

## ⚠️ MANDATORY FRONTEND PRE-READ
Before writing ANY frontend code: if `frontend/node_modules` is absent run `npm install` (in `frontend/`), then read `frontend/AGENTS.md` and the bundled docs in `frontend/node_modules/next/dist/docs/`. This is a modified Next.js 16 with breaking changes vs. training data — code written from memory will be wrong.

## Requirements
- New `frontend/src/components/rating-leaderboard.tsx` (client component):
  - Fetch `getOpportunities({ sort: "return", limit: N })` (or a dedicated rating sort) and order by `rating` desc.
  - Render a compact table: Rank (🥇🥈🥉 for top 3 via `medal`, else numeric), Strategy label (protocol + asset + type), Expected Return (% and, via capital context, $/yr), Risk (label + color), Confidence %.
  - Reuse the risk-color / ⭐ helpers from `opportunity-card.tsx` (task-07) — import if exported, else mirror the tiny logic.
  - Use shadcn `Table` primitives (already used by the old tables).
  - Loading/error/empty states.
  - Optional: clicking a row opens the detail view (task-10) via the shared `onOpenDetail` contract.

## Existing Code References
- `frontend/src/lib/api.ts` — `getOpportunities` + rating/medal/confidence fields (task-04).
- `frontend/src/components/ui/table.tsx` — shadcn Table.
- `frontend/src/components/opportunity-card.tsx` (task-07) — risk-color/⭐ helpers; `capital-context.tsx` (task-06) for $ conversion.

## Implementation Details
- Keep it presentational; data fetch via the api client (`useState/useEffect`), matching the existing pattern.
- This component is owned solely by this task; task-09 places it on the page (import + render) but does not edit it.

## Acceptance Criteria
- [ ] Leaderboard table shows Rank (🥇🥈🥉 top 3) / Strategy / Expected Return (% + $/yr) / Risk / Confidence, ordered by rating desc
- [ ] Risk color + confidence rendered consistently with the card
- [ ] Expected $ reflects the capital simulator value
- [ ] Loading/error/empty states handled
- [ ] `npm run build` succeeds (in `frontend/`)

## Dependencies
- Depends on: 04, 06, 07
- Blocks: None
