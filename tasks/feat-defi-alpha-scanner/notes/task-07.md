# Task 07: Shared Opportunity Card Component

- **Decisions**: `getRiskLabel`/`getRiskColor` are named exports (not just internal helpers) so tasks 08 and 11 can import without duplicating the thresholds. The risk dot (🟢/🟡/🔴) is a separate internal helper since callers only need the CSS color class or the label string, not the emoji.
- **Decisions**: Stars rendered as a plain string (`⭐⭐⭐⭐☆`) rather than SVG icons — keeps it a one-liner, no extra icon imports, and the task spec used star emoji notation explicitly.
- **Decisions**: `CarryOpportunityOut` doesn't expose `liquidity` or `tvl` fields in the current schema, so those headline items are omitted for carry cards (loop type also lacks explicit liquidity/TVL fields on the interface — the task mentions them but they don't exist in `api.ts`). No fabricated fields added.
- **Deviations**: The `CardFooter` import was pulled in but unused — removed. Only `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent` are used, matching actual card structure.
- **Trade-offs**: Considered splitting history/breakdown into sub-components, but the whole card is one file by spec and the sections are small enough that extraction would be premature.
- **Risks**: `opp.history!` non-null assertion used inside a block already guarded by `opp.history &&` — safe, but worth a reviewer glance.
