# Task 09: Unified Opportunity Feed / Screener + Rebuilt Landing Page

- **Decisions**: `OpportunityCard` uses `opportunity` prop (not `opp` as stated in the task summary) — matched the actual component signature from task-07. The task summary had a minor inconsistency; reading the source resolved it.
- **Decisions**: `@base-ui/react` Select `onValueChange` typed as `(value: T | null, ...)` — used the same null-guard pattern `(v) => setState(v ? (v === "all" ? "" : v) : "")` already established in `loop-table.tsx` (now deleted). The sort handler uses `if (v) setSort(v)` to keep current sort on deselect.
- **Decisions**: Detail overlay is a fixed-position panel (right-sliding drawer pattern) with a semi-transparent backdrop. Clicking the backdrop closes it. Simple, no animation library needed.
- **Decisions**: `page.tsx` became a `"use client"` component to hold `selectedOpp` state — this is the minimal change; alternately state could live in the feed, but the task spec requires `handleOpenDetail` at the page level to pass to all three sections (hero, leaderboard, feed).
- **Deviations**: None — all steps completed as specified.
- **Trade-offs**: Grid layout (2-col sm, 3-col lg) for cards vs. single column. Grid fills space better than a list and matches card-based UIs; can revert to `flex-col` if dense list is preferred.
- **Risks**: `page.tsx` is now a client component. If server-side rendering of the page shell matters in future, move the `selectedOpp` state + overlay into a separate client wrapper component.
