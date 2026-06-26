# Task 01: Expose Ranker Component Score Breakdown

## Objective
Make `score_opportunities()` return the per-component normalized scores and the weights used, so the API can surface "WHY" breakdowns (PRD #3, #5) without recomputing anything downstream.

## Context
**Quick Context:**
- `ranker.py:score_opportunities()` already computes the normalized component values in the `normalized[i]` dict, then throws them away — only `score` and `rank` end up on the output dicts (~lines 50-67).
- This task changes the ranker's return shape; `routes.py` and the response schemas consume it (touched in task-04, which depends on this).

## Requirements
- Each returned opportunity dict gains a `breakdown` key: a dict mapping each metric key (yield_score, liquidity_score, tvl_score, stability_score, utilization_penalty, volatility_penalty, protocol_risk) to its **normalized [0,1] value** (post-inversion for penalty keys).
- Each returned dict also gains a `weights` key: the weights dict actually used for scoring (so the UI can show "Yield 40% / Liquidity 25% / …").
- Preserve all existing behavior: `score`, `rank`, original input keys, sort order, tie-rank logic must be unchanged. All existing tests in `test_ranker.py` must still pass untouched.
- Keep the function pure (no I/O).

## Existing Code References
- `backend/app/calculations/ranker.py` — the only file to modify.
- `backend/tests/test_ranker.py` — existing tests + `_opp()` factory + `_DEFAULT_WEIGHTS`; mirror its style.

## Implementation Details
- Inside the scoring loop, after computing `normalized[i]`, attach `opp["breakdown"] = dict(normalized[i])` and `opp["weights"] = dict(weights)`.
- Do not change the normalization or penalty-inversion logic — just stop discarding the result.

## TDD Mode

This task uses Test-Driven Development. Write tests BEFORE implementation.

### Test Specifications
- **Test file**: `backend/tests/test_ranker.py` (extend existing)
- **Test framework**: pytest + pytest-asyncio
- **Test command**: `cd backend && pytest tests/test_ranker.py`

### Tests to Write
1. **breakdown present and normalized**: scored opp has `breakdown` with all 7 metric keys, each a float in [0,1].
2. **breakdown reflects penalty inversion**: opp with lower utilization_penalty has a HIGHER `breakdown["utilization_penalty"]` than one with higher raw penalty.
3. **weights echoed**: returned `weights` equals the weights passed in.
4. **existing behavior intact**: re-assert that `score`/`rank`/input keys are still present and ordering unchanged (can reuse an existing-style assertion).

### TDD Process
1. Write the tests above — they should FAIL (RED)
2. Implement the minimum code to make them pass (GREEN)
3. Run the full test suite to check for regressions
4. Refactor if needed while keeping tests green

### Mocking Discipline
- Mock only at the **system boundary**: paid/external APIs, network, wall clock & randomness, destructive side effects, filesystem I/O.
- Do NOT mock the code under test or internal modules it calls — `score_opportunities` is pure; test it directly with real dicts.
- Do NOT mock a layer above the real boundary.
- When mocking a boundary, the mock's shape and behavior must match the real dependency.

## Acceptance Criteria
- [ ] Each scored opportunity dict contains a `breakdown` dict with all 7 normalized metric keys, values in [0,1]
- [ ] Each scored opportunity dict contains a `weights` dict equal to the input weights
- [ ] Penalty keys in `breakdown` are inverted (lower raw penalty → higher breakdown value)
- [ ] All pre-existing `test_ranker.py` tests still pass unchanged
- [ ] Existing backend test suite still passes (`cd backend && pytest`)

## Dependencies
- Depends on: None
- Blocks: 03, 04
