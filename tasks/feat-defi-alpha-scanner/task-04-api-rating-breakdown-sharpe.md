# Task 04: Wire Breakdown + History + Rating + Sharpe into the API

## Objective
Surface everything from tasks 01-03 through the API: extend the opportunity response schemas with `breakdown`, `weights`, history aggregates, `rating`, `rating_label`, `confidence`, `medal`, and approximate `sharpe`; add a `sharpe` sort option; and mirror the new fields (plus fix the FundingSnapshotOut drift) in the frontend API types.

## Context
**Quick Context:**
- `routes.py:_fetch_loop_opportunities` / `_fetch_carry_opportunities` build opp dicts, call `score_opportunities`, then map to `LoopOpportunityOut`/`CarryOpportunityOut`. This task threads the new data through that existing flow.
- Sharpe ≈ `expected_net_yield / apy_volatility`, reusing `_volatility_map` (deposit_apy STDDEV for loops, funding_rate STDDEV for carry). Volatility 0/unknown → Sharpe `None` (no divide-by-zero). Label "approx" is a UI concern (task-07/09).
- This is the integration point all frontend tasks read from.

## Requirements
### Backend
- Extend `LoopOpportunityOut` and `CarryOpportunityOut` in `responses.py` with optional fields: `market_id: str | None` (needed by the detail view's history queries — the market is already loaded in `_fetch_*`), `breakdown: dict[str, float] | None`, `weights: dict[str, float] | None`, `rating: float | None`, `rating_label: str | None`, `confidence: float | None`, `medal: str | None`, `sharpe: float | None`, and a `history: dict | None` (the today/yesterday/avg_7d/avg_30d aggregate for that opportunity). Add a small `YieldHistoryOut` model for the history shape, or inline as a typed dict — keep ORM-free Pydantic v2 style.
- In `_fetch_loop_opportunities` / `_fetch_carry_opportunities`:
  - After `score_opportunities`, call `rate_opportunities` (task-03) on the ranked list. Populate the per-opp inputs the rating engine needs (`_protocol`, history-point count `n`).
  - Fetch history aggregates via the task-02 helper (batched over the market_ids already gathered) and attach to each opp.
  - Compute Sharpe: loops use deposit_apy volatility, carry uses funding_rate volatility (reuse/extend `_volatility_map`; today it only does funding_rate — add a parameterized variant or a sibling helper for deposit_apy). Map effective_yield/net_carry over volatility; None when volatility is 0/None.
  - Map all new fields onto the response models.
- Add `sort` query param to `/opportunities` (and reuse for `/looping` if trivial): accepted values `return` (default, current score behavior), `risk`, `confidence`, `sharpe`, `liquidity`. Sort the combined list accordingly before applying `limit`. Unknown sort → 400. Keep existing default behavior when `sort` is omitted.
- Keep all queries batched (no N+1) — follow the existing batched-query discipline in these functions.

### Frontend types (fix-in-passing + new fields)
- In `frontend/src/lib/api.ts`: add the new optional fields to `LoopOpportunityOut`/`CarryOpportunityOut` (market_id, breakdown, weights, rating, rating_label, confidence, medal, sharpe, history) matching the backend.
- **Fix the drift**: `FundingSnapshotOut` in `api.ts` is missing `asset` and `protocol` (the backend already returns them) — add them.
- Add `sort?: string` to `OppParams`.
- Do NOT add UI here — types only. (This keeps frontend tasks from colliding on `api.ts`; tasks 06-11 import these types, they don't edit them.)

## Existing Code References
- `backend/app/api/routes.py` — `_fetch_loop_opportunities` (~330-497), `_fetch_carry_opportunities` (~500-652), `_volatility_map` (~676-700), `get_opportunities` (~87-113).
- `backend/app/schemas/responses.py` — `LoopOpportunityOut` (~62), `CarryOpportunityOut` (~78), `FundingSnapshotOut` (~44).
- `backend/app/calculations/rating.py` (task-03), history helper (task-02), `ranker.py` (task-01).
- `frontend/src/lib/api.ts` — interfaces to extend.

## TDD Mode

This task uses Test-Driven Development. Write tests BEFORE implementation (backend only; api.ts type edits need no tests).

### Test Specifications
- **Test file**: `backend/tests/test_api.py` (extend existing)
- **Test framework**: pytest + pytest-asyncio
- **Test command**: `cd backend && pytest tests/test_api.py`

### Tests to Write
1. **response includes new fields**: `/opportunities` items contain rating, rating_label, confidence, breakdown, weights, sharpe, history keys.
2. **rating/label consistency**: top-ranked item's rating ≥ others; label matches its rating per thresholds.
3. **sharpe null-safe**: a market with zero/insufficient volatility yields `sharpe: null`, not an error.
4. **sort param**: `?sort=confidence` orders results by confidence desc; `?sort=bogus` returns 400; omitting `sort` preserves current default order.
5. **history attached**: each item's `history` has today/yesterday/avg_7d/avg_30d keys (values may be null on sparse data).

### TDD Process
1. Write the tests above — they should FAIL (RED)
2. Implement the minimum code to make them pass (GREEN)
3. Run the full test suite to check for regressions
4. Refactor if needed while keeping tests green

### Mocking Discipline
- Use the **real test DB / app fixtures** in `conftest.py` and the FastAPI test client — do NOT mock the DB, session, or the calculation modules. Real collaborators catch real regressions.
- Mock only true external boundaries (none expected here — collectors aren't exercised by these endpoints).
- Seed data via existing fixtures.

## Acceptance Criteria
- [ ] `/opportunities` responses include breakdown, weights, rating, rating_label, confidence, medal, sharpe, history (all optional/nullable)
- [ ] Sharpe is null (not error) when volatility is 0/unknown
- [ ] `sort` param supports return/risk/confidence/sharpe/liquidity; bogus value → 400; omitted → unchanged default
- [ ] No new N+1 queries introduced (history + volatility fetched batched)
- [ ] `frontend/src/lib/api.ts` types updated to match, FundingSnapshotOut gains asset/protocol
- [ ] Existing backend test suite still passes (`cd backend && pytest`)

## Dependencies
- Depends on: 01, 02, 03
- Blocks: 06, 07, 08, 09, 10, 11
