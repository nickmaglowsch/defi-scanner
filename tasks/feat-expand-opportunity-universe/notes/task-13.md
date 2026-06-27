# Task 13: Frontend Generic Opportunity Refactor

- **Decisions**: Made `kind` prop on `OpportunityCard` optional and deprecated rather than removing it, to avoid breaking any callers outside the task scope. The component now derives strategy type from `opp.strategy_type` directly.
- **Decisions**: Moved `STRATEGY_BADGE`/`STRATEGY_LABEL` lookup tables into each component rather than a shared module — three small tables in three files is simpler than a shared module with one import each.
- **Decisions**: Generic strategy details in `opportunity-card.tsx` and `opportunity-detail.tsx` render every key from `strategy_details` as a percentage via `fmtPct`. This is a safe default since all known detail values are rates/yields. Unknown types with non-rate fields would need a dedicated renderer added later.
- **Deviations**: Removed the unused `eslint-disable-next-line react-hooks/exhaustive-deps` comment from `opportunity-detail.tsx` — the rule wasn't triggering after the dep array was updated, so the suppress caused a lint warning.
- **Deviations**: Removed unused `CardFooter` import from `opportunity-card.tsx` (pre-existing lint warning, fixed as a cleanup).
- **Trade-offs**: The 3 pre-existing `react-hooks/set-state-in-effect` lint errors in `opportunity-feed.tsx`, `opportunity-detail.tsx`, and `capital-context.tsx` were not fixed — they pre-date this task and fixing them would require restructuring those useEffects (out of scope).
- **Risks**: The `isCarry` / `!isLoop && !isCarry` guards in `opportunity-detail.tsx` chart fetching — new strategy types produce no charts (empty data). If a future strategy type has chart data, a dedicated branch must be added.
