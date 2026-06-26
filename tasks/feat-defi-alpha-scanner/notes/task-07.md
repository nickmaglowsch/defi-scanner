# Task 07: Opportunity Engine & REST API

- **Decisions**:
  - Ranker normalizes all 7 metrics via min-max scaling across the batch. Penalty metrics (utilization, volatility, protocol_risk) are inverted as `1 - normalized` so higher raw penalty → lower contribution to score. When min==max, normalized value is 0 (neutral).
  - Orchestrator (`trigger_loop_calculation`, `trigger_carry_calculation`) is called AFTER the collector commits the snapshot transaction, in a fresh session. This avoids interfering with pre-existing test mock expectations and keeps calculation failures from rolling back snapshot writes.
  - Volatility penalty computed via SQL `STDDEV(funding_rate)` over the last N rows (default 20) — neutral 0 if insufficent rows.
  - API routes use `func.max()` + `.label()` for subquery column access instead of `text()`, which avoids SQLAlchemy `AttributeError` on `.c.max_ts`.
  - The `/opportunities` endpoint merges loop and carry results, scored separately by the ranker (each type gets its own normalization), then the combined list is sorted by score for a unified ranking.

- **Deviations**:
  - `Ranker.looping` and `Ranker.carry` in the responses schema renamed to `LoopOpportunityOut` / `CarryOpportunityOut` for consistency with the project's naming pattern.
  - The `_trigger_calc` methods in collectors use try/except so a calc failure doesn't block the collector cycle (logged as error).

- **Risks**:
  - The `/looping` and `/opportunities` endpoints run `simulate_looping`/`calculate_carry` on every request for snapshots that haven't been calculated yet (due to lazy DB addition — not from collector cycles). Under high load this could create overhead; the idempotency check prevents duplicates but not recomputation. For production: use the orchestrator call from collectors as the primary write path.
  - Volatility STDDEV query uses a simple LIMIT + STDDEV approach rather than the window function spec'd (`STDDEV OVER ROWS 20 PRECEDING`). This works correctly for the latest N rows per market but doesn't give per-row historical volatility. Sufficient for the penalty input to the ranker.
