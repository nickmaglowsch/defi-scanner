# Task 09: Frontend Dashboard

- **Decisions**: 
  - Used `"use no memo"` directive on TanStack Table components to suppress React Compiler warnings about incompatible memoization (TanStack Table v8 generates functions unsafely for React 19 compiler).
  - Used `eslint-disable react-hooks/set-state-in-effect` for data-fetching effects — the React 19 lint rule flags the pattern `setLoading(true)` in `useEffect`, but this is a legitimate, well-established pattern for data fetching. Refactoring to avoid it would add unnecessary complexity (e.g., startTransition wrappers or useReducer).
  - Types kept inline in `lib/api.ts` (~70 lines of interfaces) rather than a separate `types/` directory. Ponytail: fewer files, one import for consumers.
  - Home cards use individual `useEffect` hooks per card — each fetches independently. Could use `Promise.all` but independent hooks give partial rendering (cards appear as data arrives) for better perceived performance.
- **Deviations**: 
  - "Highest Funding" card displays `market_id` (truncated UUID) instead of an asset name. The `/funding` endpoint returns `FundingSnapshotOut` which has no `asset` field — only `market_id`. The task spec says to display "asset + annualized_funding%" but the API shape doesn't support it. `CarryOpportunityOut` (from `/opportunities?type=carry`) has `asset` + `funding_yield`, but the task said to use `/funding`. Used the specified endpoint and displayed the truncated market_id.
  - History chart uses `observed_at` → `toLocaleDateString()` for the X axis. Time-formatting can be refined later.
  - Chart market selector labels are truncated UUIDs (first 16 chars + "…"). The `/funding` endpoint returns `market_id` UUIDs only — no human-readable market name. Adding market names would require an API change or a `/markets` endpoint.
- **Trade-offs**: 
  - Client-side sorting with TanStack Table rather than server-side. The data set is bounded (max 100 rows from API), so client-side sorting is immediate and avoids extra round-trips.
  - Filters trigger API refetches (server-side filtering) rather than client-side filtering. This ensures consistency: filters narrow results at the DB level, not after the fact.
- **Risks**: 
  - The `/history` endpoint requires a valid UUID `market_id`. If `/funding` returns 0 snapshots, the market selector stays empty and the chart shows no data. This is handled gracefully.
  - Select components (`@base-ui/react/select` v4 shadcn) differ from the classic Radix-based shadcn select. The `onValueChange` callback passes `string | null`, not `string`. Wrapped all handlers with a null guard.
