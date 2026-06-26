# Task 06: Carry Calculator (TDD)

- **Decisions**: `expected_annual_return = net_carry` (as %). No notional multiplication — the function operates on yield percentages only, consistent with the looping calculator pattern. Input capital is implicit (handled by the API layer that applies this to notional).
- **Deviations**: None. Followed the task spec formula exactly.
- **Trade-offs**: `risk_score` uses a linear heuristic (`abs(funding_yield)*0.3 + abs(borrow_cost)*0.2`) which is unbounded — values can exceed 1.0. The ranker (task-07) may normalize/clamp when combining with the volatility component.
- **Risks**: Unbounded risk_score. If the ranker expects values in [0,1], the ranker should clamp. Marked with a `ponytail:` comment in the source.
