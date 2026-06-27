# Task 08 — Generic Opportunity Schema and API Refactor

## Objective

Replace the `LoopOpportunityOut | CarryOpportunityOut` union with a single generic `OpportunityOut` schema and update the API routes to use it.

## Context

Planning decision Q5-B requires a unified response model with a `strategy_type` discriminator. This is a wide-reaching refactor touching schemas, routes, calculations, and tests.

## Requirements

1. In `backend/app/schemas/responses.py`:
   - Add a generic `OpportunityOut` with fields common to all strategies plus a `strategy_type` discriminator.
   - Include `strategy_details` as a dict/JSONB-like field for strategy-specific values (loop leverage, carry funding yield, cross-protocol market IDs, etc.).
   - Keep `LoopOpportunityOut` and `CarryOpportunityOut` as deprecated aliases or remove them after internal refactor.
   - Add `percentile_90d` and `historical_rank` fields for future anomaly context.
2. Update `backend/app/api/routes.py`:
   - `_fetch_loop_opportunities`, `_fetch_carry_opportunities`, and the new cross-protocol path must return `OpportunityOut`.
   - `rerate_combined` continues to work on the generic list.
   - Update sorting keys to handle generic fields.
3. Update `backend/app/calculations/ranker.py` if needed to preserve extra fields.
4. Update `backend/app/calculations/rating.py` to work with generic opportunity dicts.
5. Update all backend tests that assert on response shape.
6. Update `frontend/src/lib/api.ts` to match the new generic schema and add a discriminated union helper.

## Target Files

- `backend/app/schemas/responses.py`
- `backend/app/api/routes.py`
- `backend/app/calculations/ranker.py`
- `backend/app/calculations/rating.py`
- `backend/tests/test_api.py`
- `backend/tests/test_ranker.py`
- `backend/tests/test_rating.py`
- `frontend/src/lib/api.ts`

## Dependencies

- Task 01 (new calculation tables exist)
- Task 03-07 (adapters produce data; not strictly required for schema work but required for integration)

## TDD Mode

Yes.

- Write tests for the new `OpportunityOut` schema serialization and route response shape first.
- Update existing tests to expect the generic schema.

## Acceptance Criteria

1. `GET /api/v1/opportunities` returns a list of `OpportunityOut` objects with `strategy_type` in `{loop, carry}`.
2. Frontend TypeScript compiles against the new `api.ts` types.
3. All backend tests pass.
4. `rerate_combined` still assigns unique medals across strategy types.

## Notes

- `strategy_details` keeps the schema extensible for future strategy types without schema changes.
- Preserve existing response fields where possible to minimize frontend churn; map old loop/carry fields into `strategy_details`.
