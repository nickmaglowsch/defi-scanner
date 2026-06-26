# Task 01: Expose Ranker Component Score Breakdown

- **Decisions**: Added `opp["breakdown"] = dict(normalized[i])` and `opp["weights"] = dict(weights)` inside the existing scoring loop, immediately after the score total is computed. `dict()` copies avoid callers mutating the internal normalized list.
- **Deviations**: None — exactly the two-liner the task spec described.
- **Trade-offs**: Could have returned breakdown/weights as separate return values from `score_opportunities`, but mutating the opp dict in-place matches the existing pattern (score and rank are already added the same way).
- **Risks**: None — pure function, no I/O, no normalization logic changed.
