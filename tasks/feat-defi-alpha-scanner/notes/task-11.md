# Task 11: Rating Leaderboard

- **Decisions**: Used a plain colored dot (`<span className="inline-block h-2 w-2 rounded-full bg-current" />`) for the risk indicator rather than the emoji dots from `opportunity-card.tsx` — `getRiskColor` returns a Tailwind text-color class which works cleanly with `bg-current`, keeping the table compact. The `getRiskDot` helper in that file is not exported so this avoids re-implementing it.
- **Deviations**: None — implemented exactly as specified.
- **Trade-offs**: Skipped TanStack Table — `shadcn Table` primitives are sufficient for a static sorted list; TanStack adds no value here (no sorting, filtering, or pagination needed for 10 rows).
- **Risks**: `getRiskColor` returns Tailwind class strings; the dot approach works only if those class names are included in Tailwind's scan. They are (used elsewhere in `opportunity-card.tsx`), so no purge risk.
