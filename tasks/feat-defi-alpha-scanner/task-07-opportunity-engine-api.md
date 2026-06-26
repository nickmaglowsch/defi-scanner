# Task 07: Opportunity Engine & REST API

## Objective
Implement the opportunity ranker (TDD for pure scoring), all 6 REST API endpoints, and Pydantic response schemas. Wire calculations (looping, carry) into the DB write path so snapshots trigger calculation runs.

## Context
This is the integration hub: it reads snapshot data from the DB, runs the looping and carry calculators on the latest snapshots, stores results, scores + ranks opportunities, and serves everything via the REST API. The ranker is pure math (TDD); the API layer is thin DB queries (test-after). See `updated-prd.md` Sections "REST API Endpoints", "Calculation Engine → Opportunity Ranker", and "Opportunity Engine → ranking formula".

**Quick Context**:
- Uses `simulate_looping` from task-05 and `calculate_carry` from task-06.
- DB models from task-02: all tables.
- Volatility computation: `STDDEV(funding_rate)` over last 20 snapshots per market, via SQL window function. Neutral/zero if < 20 rows.
- RANKER_WEIGHTS from config (JSON string → dict). Default: all weights = 1.0.

## Target Files
- `backend/app/calculations/ranker.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/responses.py`
- `backend/app/api/__init__.py`
- `backend/app/api/routes.py`
- `backend/tests/test_ranker.py`
- `backend/tests/test_api.py`

## Dependencies
- task-02 (DB models + session)
- task-05 (looping calculator)
- task-06 (carry calculator)
- task-03 (Aave adapter — not a code dep, but API queries lending_snapshots; empty DB returns empty arrays, which is fine)
- task-04 (same for funding_snapshots)

## Steps

### Part A: Opportunity Ranker (TDD)
1. Write `backend/tests/test_ranker.py` FIRST (RED):
   - Tests listed in TDD section below.
2. Write `backend/app/calculations/ranker.py` (GREEN):
   - Function: `score_opportunities(opportunities: list[dict], weights: dict) -> list[dict]`
   - Each opportunity dict has: `yield_score`, `liquidity_score`, `tvl_score`, `stability_score`, `utilization_penalty`, `volatility_penalty`, `protocol_risk`.
   - For each metric: normalize to 0-1 range across the batch (min-max normalization). For penalties (utilization, volatility, protocol_risk): invert so higher penalty = lower score.
   - `total_score = sum(weights[k] * normalized[k] for k in weights)`
   - Sort descending by total_score, assign rank, return.
   - Edge cases: empty list → empty list; single opportunity → rank 1 with normalized values = 0 or 1; all identical → all same rank.
3. Run ranker tests → GREEN. Refactor.

### Part B: Pydantic Schemas
4. Write `backend/app/schemas/responses.py`:
   - Pydantic v2 `BaseModel` classes for each response type:
     - `ProtocolOut`: id, name, type, chain, risk_score
     - `MarketOut`: id, protocol_id, asset, market_type
     - `LendingSnapshotOut`: id, market_id, observed_at, deposit_apy, borrow_apy, utilization, available_liquidity, total_supplied, total_borrowed, tvl
     - `FundingSnapshotOut`: id, market_id, observed_at, funding_rate, annualized_funding, open_interest, volume_24h, long_short_ratio, mark_price, index_price
     - `LoopOpportunityOut`: protocol, asset, deposit_apy, borrow_apy, effective_yield, leverage, safety_margin, liquidation_distance, risk_score, score, rank
     - `CarryOpportunityOut`: protocol, asset, funding_yield, spot_yield, borrow_cost, trading_fees, net_carry, risk_score, score, rank
     - `HistoryPointOut`: observed_at, value (generic for chart data)
     - `AlertOut`: id, alert_type, threshold_value, triggered_value, market_id, channel, status, fired_at
   - Use `model_config = ConfigDict(from_attributes=True)` for ORM compatibility.

### Part C: API Routes
5. Write `backend/app/api/routes.py` (all 6 endpoints in one file — ponytail):
   - Create `router = APIRouter(prefix="/api/v1")`.
   - **GET /opportunities**: Query params `type`, `asset`, `protocol`, `min_yield`, `min_liquidity`, `limit` (default 20).
     - For each type: fetch latest snapshots + run calculations (if not already cached for this snapshot), score via ranker, return ranked list.
     - Join markets and protocols for display names.
   - **GET /looping**: Same pattern, filtered to loop opportunities only. Params: `asset`, `protocol`, `min_yield`, `min_liquidity`, `limit`.
     - Query latest `lending_snapshots` per market, run `simulate_looping` with default inputs (capital=10000, target_ltv=0.7, safety_buffer=0.95, max_loops=20), store result in `loop_calculations`, return.
     - Upsert: if a `loop_calculation` already exists for this `lending_snapshot_id` with same `calc_version`, skip recomputation.
   - **GET /funding**: Latest funding rates. Params: `asset`, `protocol`, `limit`.
     - Query `funding_snapshots` ordered by `observed_at DESC`, join markets.
   - **GET /history**: Time-series data for charts. Params: `type` (funding|lending), `market_id` (required), `from`, `to`, `limit` (default 100).
     - If `type=funding`: query `funding_snapshots` for market, return `[{observed_at, funding_rate}]`.
     - If `type=lending`: query `lending_snapshots` for market, return `[{observed_at, deposit_apy, borrow_apy}]`.
     - Add query for `annualized_funding` as an alternatitve `field` param for the chart.
   - **GET /protocols**: `SELECT * FROM protocols` → list.
   - **GET /assets**: `SELECT DISTINCT asset FROM markets` → list.
   - All endpoints use `Depends(get_db)` for async DB sessions.
   - Add CORS already handled in main.py (task-01).
6. Register router in `backend/app/main.py`:
   ```python
   from app.api.routes import router as api_router
   app.include_router(api_router)
   ```

### Part D: API Tests
7. Write `backend/tests/test_api.py`:
   - Use `httpx.AsyncClient` (or FastAPI `TestClient` with `pytest-asyncio`) against the FastAPI app with a test DB.
   - Test each endpoint:
     - `/opportunities?type=loop&limit=5` → returns ≤5 items, ranked, with score field.
     - `/looping?asset=USDC` → filters by asset.
     - `/funding?limit=3` → returns ≤3 items.
     - `/history?type=funding&market_id=<uuid>` → returns time-series array.
     - `/protocols` → returns non-empty list.
     - `/assets` → returns non-empty list.
   - Test edge cases: missing params → 200 with empty array; invalid UUID → 400; unknown type → 400.
   - Use DB fixtures that insert sample protocols, markets, and a few snapshots.

## TDD Mode (ranker only)

This task uses Test-Driven Development for the opportunity ranker. Write ranker tests BEFORE ranker implementation.

### Test Specifications (ranker)
- **Test file**: `backend/tests/test_ranker.py`
- **Test framework**: pytest
- **Test command**: `pytest tests/test_ranker.py -v`

### Tests to Write (ranker)
1. **Basic ranking**: 3 opportunities with different yields → highest yield gets rank 1.
2. **Equal scores**: 2 opportunities with identical metrics → same rank.
3. **Empty input**: empty list → empty list returned.
4. **Single opportunity**: one item → rank 1, normalized values handled.
5. **Weight influence**: weight_yield=10, weight_liquidity=0 → yield dominates ranking.
6. **Penalty inversion**: high utilization_penalty → lower total score (all else equal).
7. **Deterministic output**: same inputs + weights → identical output.

### TDD Process (ranker)
1. Write the tests above — they should FAIL (RED)
2. Implement `score_opportunities()` to make them pass (GREEN)
3. Run the full test suite to check for regressions
4. Refactor if needed while keeping tests green

### Mocking Discipline (ranker)
- No mocking — pure function on dict inputs.

## Acceptance Criteria
- [ ] All 6 API endpoints return correct HTTP status codes and JSON shapes
- [ ] `/opportunities` returns ranked list with scores, supports `type`, `asset`, `protocol`, `limit` filters
- [ ] `/looping` triggers looping simulator on latest snapshots, stores results in `loop_calculations`, idempotent (same snapshot+calc_version → no duplicate calc)
- [ ] `/history?type=funding&market_id=X` returns time-series array ordered by observed_at
- [ ] `/protocols` and `/assets` return populated lists after collector cycles
- [ ] Opportunity ranker correctly sorts by weighted score; penalty metrics reduce score
- [ ] Ranker handles edge cases: empty, single, ties
- [ ] `calc_version` stored on all calculation rows ("loop-v1", "carry-v1")
- [ ] Pydantic response schemas validate output shape (no ORM leakage)
- [ ] All ranker tests pass: `pytest tests/test_ranker.py -v`
- [ ] All API tests pass: `pytest tests/test_api.py -v`
- [ ] Full test suite passes: `pytest -v`
