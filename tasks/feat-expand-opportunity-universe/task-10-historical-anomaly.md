# Task 10 — Historical Percentile and Rank Computation

## Objective

Add on-demand historical context to opportunities: 90-day percentile and historical rank against existing snapshot history.

## Context

Planning decision Q7-A computes these fields from existing history rather than adding new storage. This task implements the computation and exposes it in API responses.

## Requirements

1. Extend `backend/app/calculations/history_agg.py` with:
   - `get_percentile(db, market_ids, table, field, window_days=90)` returning per-market percentile of the latest value within the window.
   - `get_historical_rank(db, market_ids, table, field, window_days=90)` returning per-market rank (e.g. "highest in 90 days", "top 5%").
2. Update `backend/app/api/routes.py`:
   - Attach `percentile_90d` and `historical_rank` to `OpportunityOut` for loop, carry, stable, and cross-protocol opportunities where history exists.
   - Leave fields `null` when history is insufficient (< 7 days or < 20 points).
3. Update `backend/app/schemas/responses.py` so `OpportunityOut` includes `percentile_90d: float | None` and `historical_rank: str | None`.
4. Add tests for percentile/rank computation using seeded snapshot history.

## Target Files

- `backend/app/calculations/history_agg.py`
- `backend/app/api/routes.py`
- `backend/app/schemas/responses.py`
- `backend/tests/test_history_agg.py`
- `frontend/src/lib/api.ts`

## Dependencies

- Task 08 (generic `OpportunityOut`)

## TDD Mode

Yes.

- Write tests for `get_percentile` and `get_historical_rank` against real SQL history fixtures.

## Acceptance Criteria

1. `pytest backend/tests/test_history_agg.py` passes.
2. `/opportunities` responses include `percentile_90d` and `historical_rank` when history is deep enough.
3. Fields are `null` when history is insufficient.
4. Frontend types include the new fields.

## Notes

- Use existing TimescaleDB hypertables; windowed percentile can be computed with `PERCENT_RANK()` or simple bucket counting.
- Historical rank can be a human-readable string like "99th percentile (90d)".
