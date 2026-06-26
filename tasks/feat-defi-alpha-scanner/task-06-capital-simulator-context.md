# Task 06: Capital Simulator Context + Provider

## Objective
Provide global capital state (default $20,000, localStorage-persisted) via a React context, plus a top-right input control and a yield→dollars helper, for use by every opportunity card (PRD #7).

## Context
**Quick Context:**
- Frontend uses plain `useState/useEffect + fetch` — no react-query, no existing global state. This is the app's first context provider; it will be mounted at the app root (the root layout) so all pages/cards can read it.
- The card (task-07) and feed/hero/leaderboard consume this; this task owns the context + provider + input control + the conversion helper. Nothing else edits these files.

## ⚠️ MANDATORY FRONTEND PRE-READ
Before writing ANY frontend code: if `frontend/node_modules` is absent run `npm install` (in `frontend/`), then read `frontend/AGENTS.md` and the bundled docs in `frontend/node_modules/next/dist/docs/`. This is a modified Next.js 16 with breaking changes vs. training data — code written from memory will be wrong. **Confirm the correct App Router root-layout / provider mounting pattern from the bundled docs before wiring the provider.**

## Requirements
- New `frontend/src/lib/capital-context.tsx` (client component):
  - `CapitalProvider` holding `capital: number`, `setCapital`, default **20000**, hydrated from and persisted to `localStorage` (key e.g. `defi-capital`). Guard SSR (only touch localStorage in effect / on client).
  - `useCapital()` hook returning `{ capital, setCapital }`.
  - Export a pure helper `yieldToDollars(returnPct: number, capital: number): { perYear: number; perMonth: number }` = `capital × returnPct/100` and `/12`.
- New `frontend/src/components/capital-input.tsx`: a top-right numeric input bound to the context (uses shadcn `Input`).
- Mount `CapitalProvider` at the app root (root layout) so all routes are wrapped. (Adding the provider to the root layout is the ONLY edit this task makes outside its own new files — task-09 owns `page.tsx` content, not the layout wrapper.)

## Existing Code References
- `frontend/src/components/ui/input.tsx` — shadcn Input.
- `frontend/src/app/layout.tsx` — root layout (wrap with provider; verify the modified-Next layout conventions from the bundled docs first).

## Implementation Details
- localStorage hydration must not cause hydration mismatch: initialize state to the default, then load from localStorage in an effect, or use a mounted guard. Follow whatever SSR-safe pattern the bundled Next docs recommend.
- Keep `yieldToDollars` pure so cards can call it directly.

## Acceptance Criteria
- [ ] `useCapital()` returns capital defaulting to 20000, persisted to localStorage across reloads
- [ ] Capital input in the top-right updates the shared value live
- [ ] `yieldToDollars(11.4, 20000)` → `{ perYear: 2280, perMonth: 190 }`
- [ ] No SSR/hydration warnings; provider wraps the whole app
- [ ] `npm run build` succeeds (in `frontend/`)

## Dependencies
- Depends on: None
- Blocks: 07
