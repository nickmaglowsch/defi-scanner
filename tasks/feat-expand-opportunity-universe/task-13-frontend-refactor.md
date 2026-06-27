# Task 13 — Frontend Generic Opportunity Refactor

## Objective

Refactor the frontend to use the generic `OpportunityOut` schema across all components and add UI support for new strategy types and filters.

## Context

Planning decision Q11-A is a big-bang refactor. The frontend currently discriminates opportunities by `effective_yield` and renders Loop/Carry cards. It must now handle an arbitrary `strategy_type`.

## Requirements

1. Update `frontend/src/lib/api.ts`:
   - Replace `LoopOpportunityOut` / `CarryOpportunityOut` with a single `OpportunityOut` interface using a `strategy_type` discriminator.
   - Update `isLoop()` / `oppYield()` helpers to use `strategy_type`.
   - Add `getStableLending`, `getStaking`, `getRestaking`, `getPendle`, `getCrossProtocol` typed helpers if dedicated endpoints are added; otherwise use `getOpportunities({ type })`.
2. Update `frontend/src/lib/opportunities-context.tsx` to use `OpportunityOut`.
3. Update `frontend/src/components/opportunity-card.tsx`:
   - Render strategy-specific details from `strategy_details`.
   - Show strategy badge (Loop, Carry, Stable Lending, Staking, Restaking, Pendle, Cross-Protocol).
   - Keep existing Loop/Carry math expanders for backward-compatible strategy details.
4. Update `frontend/src/components/terminal-hero.tsx` and `rating-leaderboard.tsx` to use the new type and display strategy labels.
5. Update `frontend/src/components/opportunity-feed.tsx`:
   - Add `strategy_type` filter options.
   - Update sort options if new fields are added.
6. Update `frontend/src/components/opportunity-detail.tsx` to render strategy-specific content from `strategy_details`.
7. Run `npx tsc --noEmit` and `npm run lint` to verify.

## Target Files

- `frontend/src/lib/api.ts`
- `frontend/src/lib/opportunities-context.tsx`
- `frontend/src/components/opportunity-card.tsx`
- `frontend/src/components/opportunity-detail.tsx`
- `frontend/src/components/terminal-hero.tsx`
- `frontend/src/components/rating-leaderboard.tsx`
- `frontend/src/components/opportunity-feed.tsx`

## Dependencies

- Task 08 (generic backend schema)
- Task 09 (cross-protocol strategy_type)
- Task 10 (percentile fields)
- Task 11 (new strategy types)

## TDD Mode

No.

- There is no frontend test harness. Verification is via TypeScript compilation and manual UI inspection.

## Acceptance Criteria

1. `npx tsc --noEmit` in `frontend/` passes.
2. `npm run lint` passes.
3. `npm run build` succeeds.
4. The opportunity feed filter includes the new strategy types.
5. Existing Loop/Carry cards render without regression.

## Notes

- Follow `frontend/AGENTS.md`: read `node_modules/next/dist/docs/` after `npm install` if Next.js APIs are used.
- Strategy details should be rendered defensively; unknown strategy types fall back to a generic display.
