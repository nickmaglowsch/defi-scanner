# Task 09 — Cross-Protocol Calculation Engine

## Objective

Implement cross-protocol spread detection by pairing lending markets and persisting results in `CrossProtocolCalculation`.

## Context

Planning decision Q6-B requires a persisted calculation table. This task builds the calculation logic and API support.

## Requirements

1. Create `backend/app/calculations/cross_protocol.py` with a pure function `calculate_cross_protocol_spread(deposit_apy, borrow_apy, max_ltv, liq_threshold, ...)` returning net spread, implied leverage, safety margin, and risk score.
2. Create `backend/app/calculations/orchestrator.py::trigger_cross_protocol_calculation` (or add to existing orchestrator):
   - Triggered after a new lending snapshot is written.
   - Finds the best deposit market for the same asset on a different protocol and the best borrow market on a different protocol.
   - Avoids pairing a market with itself.
   - Persists a `CrossProtocolCalculation` row idempotently.
3. Update `backend/app/api/routes.py`:
   - `_fetch_cross_protocol_opportunities` returns `OpportunityOut` with `strategy_type="cross_protocol"`.
   - Include in `/opportunities?type=all`.
4. Update `backend/app/schemas/responses.py` if cross-protocol needs additional response fields.
5. Add tests for the pure calculation and the route.

## Target Files

- `backend/app/calculations/cross_protocol.py` (new)
- `backend/app/calculations/orchestrator.py`
- `backend/app/api/routes.py`
- `backend/app/schemas/responses.py`
- `backend/tests/test_cross_protocol.py` (new)

## Dependencies

- Task 01 (`CrossProtocolCalculation` table)
- Task 08 (generic `OpportunityOut`)

## TDD Mode

Yes.

- Write a failing test for `calculate_cross_protocol_spread` with sample inputs.
- Write a route test that mocks two markets and asserts a cross-protocol opportunity is returned.

## Acceptance Criteria

1. `pytest backend/tests/test_cross_protocol.py` passes.
2. A cross-protocol opportunity has `strategy_type="cross_protocol"` and `strategy_details` containing deposit protocol/asset and borrow protocol/asset.
3. Calculation is idempotent: re-running does not create duplicate rows.
4. `/opportunities?type=all` includes cross-protocol results after `rerate_combined`.

## Notes

- Start with same-asset cross-protocol spreads only (e.g. deposit USDC on Aave, borrow USDC on Morpho).
- Cross-asset spreads are out of scope for this build.
- Risk score should penalize using different protocols and chains.
