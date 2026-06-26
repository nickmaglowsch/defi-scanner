# Task 08: Terminal-Style "Today's Best Opportunities" Hero

- **Decisions**: Used inline dot character `●` styled with Tailwind color classes instead of emoji dots (🟢/🟡/🔴) — emoji render inconsistently across terminal-adjacent dark backgrounds. The `getRiskColor` class was mapped to `text-green-400/yellow-400/red-400` to stay consistent with the terminal palette (original uses 500 variants; 400 is lighter and reads better on `bg-zinc-950`).
- **Deviations**: None from spec.
- **Trade-offs**: `isLoop` type guard uses `"effective_yield" in opp` duck-typing rather than a `type` field — matches how the existing codebase distinguishes loop vs carry (no explicit discriminant field exists on the union).
- **Risks**: `getRiskColor` returns CSS class strings like `text-green-500`; the dot-color mapping does a simple `.includes("green")` substring check. If that helper ever adds new classes with "green" in an unexpected position, the mapping could be wrong — but the helper is trivially small and stable.
