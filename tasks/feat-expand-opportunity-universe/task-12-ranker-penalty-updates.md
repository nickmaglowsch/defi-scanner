# Task 12 — Ranker and Rating Penalty Metric Updates

## Objective

Extend the ranker to support strategy-specific penalty metrics and update rating to account for them transparently.

## Context

Planning decision Q10-B adds explicit penalty metrics for new risk dimensions. The existing ranker min-max normalizes a fixed set of keys. We need it to be driven by configuration while remaining backward-compatible.

## Requirements

1. Update `backend/app/calculations/ranker.py`:
   - Accept any set of metric keys from `weights`, including new penalty keys.
   - Treat keys ending in `_penalty` as penalties (inverted normalization) in addition to the hardcoded `PENALTY_KEYS` set.
   - Preserve existing behavior for current weights.
2. Update `backend/app/config.py`:
   - Extend `RANKER_WEIGHTS` default JSON to include optional strategy-specific penalties:
     - `cross_protocol_penalty`
     - `slashing_penalty`
     - `bridge_penalty`
     - `maturity_penalty`
3. Update `backend/app/api/routes.py` to populate penalty values for each strategy type in the `opp` dict before scoring.
4. Update `backend/app/schemas/responses.py` so `breakdown` can include new penalty keys.
5. Add/update tests for ranker with custom penalty keys and for route penalty population.

## Target Files

- `backend/app/calculations/ranker.py`
- `backend/app/config.py`
- `backend/app/api/routes.py`
- `backend/app/schemas/responses.py`
- `backend/tests/test_ranker.py`
- `backend/tests/test_api.py`

## Dependencies

- Task 08 (generic `OpportunityOut`)
- Task 09 (cross-protocol penalties)
- Task 11 (new strategy types)

## TDD Mode

Yes.

- Write a test that passes a weights dict with a new `_penalty` key and asserts it is inverted.
- Write a route test asserting penalty values appear in the breakdown.

## Acceptance Criteria

1. `pytest backend/tests/test_ranker.py backend/tests/test_api.py` passes.
2. The ranker correctly inverts any key ending in `_penalty`.
3. Cross-protocol, staking, restaking, and Pendle opportunities include relevant penalty values in their breakdown.
4. Existing weights JSON still produces the same scores as before.

## Notes

- Keep default weights conservative; new penalties default to small weights so they do not dominate the score.
- Penalty values should typically be in [0, 1] but the ranker min-max handles any range.
