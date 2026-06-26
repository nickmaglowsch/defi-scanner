# Task 06: Carry Calculator (TDD)

## Objective
Implement the carry trade calculator — a pure, deterministic function that computes net carry from spot yield, funding yield, borrow cost, and trading fees. Delivered via TDD.

## Context
The carry calculator is the second core calculation, powering the "Best Carry" card and Carry Opportunities table. Pure math: no I/O, no DB. Inputs are individual yield/cost components; output matches `carry_calculations` columns. See `updated-prd.md` "Calculation Engine → Carry Calculator".

Calculation version: `"carry-v1"`.

**Quick Context**:
- The function is imported by task-07 (API + ranker) which writes results to DB.
- Risk score includes a volatility input — but the pure calculator doesn't query the DB. The ranker (task-07) handles the volatility computation from snapshots. The carry calculator computes a partial risk score from available inputs (e.g., borrow cost ratio, funding rate magnitude).

## Target Files
- `backend/app/calculations/carry.py`
- `backend/tests/test_carry.py`

## Dependencies
- task-02 (for `CarryCalculation` model type reference)
- task-05 (for test patterns — not a blocker, just established conventions)

## Steps
1. Write `backend/tests/test_carry.py` FIRST (RED phase):
   - Tests must cover the scenarios listed in "Tests to Write" below.
   - Run `pytest tests/test_carry.py -v` → all fail.
2. Write `backend/app/calculations/carry.py` (GREEN phase):
   - Function signature: `calculate_carry(spot_yield: float, funding_yield: float, borrow_cost: float, trading_fees: float) -> dict`
   - Algorithm:
     ```python
     net_carry = funding_yield + spot_yield - borrow_cost - trading_fees
     expected_annual_return = net_carry
     # Risk score: magnitude of funding rate volatility proxy + borrow cost ratio
     risk_score = abs(funding_yield) * 0.3 + abs(borrow_cost) * 0.2
     ```
   - Outputs (matching `CarryCalculation` fields):
     - `spot_yield`, `funding_yield`, `borrow_cost`, `trading_fees` (echo inputs)
     - `net_carry = funding_yield + spot_yield - borrow_cost - trading_fees`
     - `risk_score` (computed as above — ponytail: simple heuristic, volatility from DB added by ranker)
     - `expected_annual_return = net_carry`
   - `calc_version = "carry-v1"` in return dict.
3. Run tests → all GREEN. Refactor if needed.
4. Run full test suite: `pytest` → no regressions.

## TDD Mode

This task uses Test-Driven Development. Write tests BEFORE implementation.

### Test Specifications
- **Test file**: `backend/tests/test_carry.py`
- **Test framework**: pytest + pytest-asyncio
- **Test command**: `pytest tests/test_carry.py -v`

### Tests to Write
1. **Positive carry**: spot=5%, funding=10%, borrow=3%, fees=0.1% → net_carry=11.9%.
2. **Negative carry**: spot=1%, funding=-5%, borrow=3%, fees=0.1% → net_carry=-7.1% (losing trade).
3. **Zero-all inputs**: returns dict with zeros, no crash.
4. **Only funding positive**: spot=0, borrow=0, fees=0, funding=8% → net_carry=8%.
5. **High trading fees swamp yield**: spot=2%, funding=1%, borrow=0, fees=5% → net_carry=-2%.
6. **Risk score monotonic**: higher absolute funding rate → higher risk_score.
7. **Deterministic output**: same inputs → identical outputs.
8. **Return dict includes calc_version = "carry-v1"**: verify version string present.

### TDD Process
1. Write the tests above — they should FAIL (RED)
2. Implement the minimum code to make them pass (GREEN)
3. Run the full test suite to check for regressions
4. Refactor if needed while keeping tests green

### Mocking Discipline
- No mocking needed — pure function, no I/O.

## Acceptance Criteria
- [ ] `calculate_carry(...)` returns dict with 8 output keys (+ calc_version)
- [ ] `net_carry = funding_yield + spot_yield - borrow_cost - trading_fees` (correct formula)
- [ ] Positive carry scenario: net_carry > 0 when funding + spot > borrow + fees
- [ ] Negative carry scenario: net_carry < 0 when costs exceed yields
- [ ] Zero inputs → zero outputs, no division by zero
- [ ] Risk score increases with absolute funding rate magnitude
- [ ] Deterministic: same inputs → same outputs
- [ ] `calc_version` == `"carry-v1"` in return dict
- [ ] All 8 tests pass: `pytest tests/test_carry.py -v`
- [ ] Full test suite still passes after implementation
