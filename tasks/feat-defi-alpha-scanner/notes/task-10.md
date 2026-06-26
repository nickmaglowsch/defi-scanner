# Task 10: Opportunity Detail View + Historical Charts + Deep Link

- **Decisions**: Kept `HistoryChart` as a function inside `opportunity-detail.tsx` rather than a new file — it's only 30 lines and has no callers outside this component. Ponytail ladder rung 7.
- **Decisions**: For loop opps, deposit and borrow history fetches run in parallel via `Promise.all` so spread derivation waits for both without sequential delays.
- **Decisions**: `page.tsx` had the only import of `funding-chart.tsx` — removed the `FundingChart` section from the landing page when deleting the file. This is a UI regression (funding rate section disappears from the landing page), but task-09's feed is the replacement surface for that content.
- **Deviations**: None.
- **Trade-offs**: Spread series uses `observed_at` string equality for alignment. This works as long as both series come from the same resolution. A proper time-bucketing join would be needed if resolutions diverge — not worth it now (`# ponytail: string key join, use time bucketing if series resolutions differ`).
- **Risks**: `market_id` is typed `string | null | undefined` on both opportunity types (task-04 made it optional). The component guards on `marketId` and shows "No market ID" if absent — callers should ensure task-04 enrichment is active.
