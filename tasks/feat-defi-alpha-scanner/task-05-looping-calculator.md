# Task 05: Looping Simulator (TDD)

## Objective
Implement the leveraged looping simulator — a pure, deterministic function that computes effective yield from recursive deposit→borrow→deposit cycles. Delivered via TDD: tests first, then implementation.

## Context
The looping simulator is the core calculation for the "Best Loop" opportunity card and the Loop Opportunities table. It is pure math: no I/O, no DB, no network. Inputs are individual APY rates + user configuration; outputs are the metrics stored in `loop_calculations` rows. See `updated-prd.md` "Calculation Engine → Looping Simulator".

Calculation version: `"loop-v1"`. This string must be stored alongside results so historical calculations are reproducible even if the formula evolves.

**Quick Context**:
- Models from task-02: `LoopCalculation` (stores results after simulation — this task only needs the pure function, not DB writes).
- The function is imported by task-07 (API + ranker) which writes results to DB.
- Configurable parameters: `max_loops` default, `ltv_usage_ratio` (fraction of max LTV to use per loop).

## Target Files
- `backend/app/calculations/__init__.py`
- `backend/app/calculations/looping.py`
- `backend/tests/test_looping.py`

## Dependencies
- task-02 (for `LoopCalculation` model type reference — the function returns a dict matching its fields)

## Steps
1. Write `backend/tests/test_looping.py` FIRST (RED phase):
   - Tests must cover the scenarios listed in "Tests to Write" below.
   - Run `pytest tests/test_looping.py -v` → all fail (function doesn't exist yet).
2. Write `backend/app/calculations/looping.py` (GREEN phase):
   - Function signature: `simulate_looping(deposit_apy: float, borrow_apy: float, max_ltv: float, liquidation_threshold: float, initial_capital: float, target_ltv: float, safety_buffer: float, max_loops: int) -> dict`
   - Algorithm:
     ```python
     ltv_used = max_ltv * 0.9  # ponytail: 90% of max LTV per loop, conservative default
     total_deposited = initial_capital
     total_borrowed = 0.0
     for _ in range(max_loops):
         borrowable = total_deposited * ltv_used
         new_borrow = borrowable - total_borrowed
         if new_borrow <= 0:
             break
         total_borrowed += new_borrow
         total_deposited += new_borrow
         effective_ltv = total_borrowed / total_deposited if total_deposited > 0 else 0
         if effective_ltv >= target_ltv * safety_buffer:
             break
     ```
   - Outputs (matching `LoopCalculation` fields):
     - `deposited_capital = total_deposited`
     - `borrowed_capital = total_borrowed`
     - `net_apy = (total_deposited * deposit_apy - total_borrowed * borrow_apy) / initial_capital`
     - `effective_yield = net_apy` (same metric, different name)
     - `leverage = total_deposited / initial_capital`
     - `safety_margin = liquidation_threshold - effective_ltv`
     - `liquidation_distance = (1 - effective_ltv / liquidation_threshold) * 100` (percentage drop before liquidation)
     - `risk_score = 1 / safety_margin if safety_margin > 0 else 10.0` (simple inverse, higher = riskier)
   - `calc_version = "loop-v1"` included in return dict.
3. Run tests → all GREEN. Refactor if needed (keep tests green).
4. Run full test suite: `pytest` → no regressions.

## TDD Mode

This task uses Test-Driven Development. Write tests BEFORE implementation.

### Test Specifications
- **Test file**: `backend/tests/test_looping.py`
- **Test framework**: pytest + pytest-asyncio
- **Test command**: `pytest tests/test_looping.py -v`

### Tests to Write
1. **Single-loop leverage**: deposit_apy=5%, borrow_apy=3%, max_ltv=80%, init=1000, target=50% → loops ~1-2 times, net_apy > deposit_apy (leverage amplifies yield).
2. **Zero APY spread**: deposit_apy == borrow_apy → net_apy == deposit_apy (no benefit from looping).
3. **Negative carry**: borrow_apy > deposit_apy → net_apy < deposit_apy (looping loses money).
4. **Max loops reached**: small LTV, large target → hits max_loops limit, doesn't infinite-loop.
5. **Safety buffer stops early**: target_ltv=80%, safety_buffer=0.95 → stops when effective LTV reaches 76%.
6. **Zero initial capital**: returns zeros, no division by zero.
7. **Liquidation distance calculation**: verify formula: `(1 - effective_ltv / liquidation_threshold) * 100`.
8. **Deterministic output**: same inputs → identical outputs (no randomness, no state).
9. **Return dict includes calc_version = "loop-v1"**: verify version string present.

### TDD Process
1. Write the tests above — they should FAIL (RED)
2. Implement the minimum code to make them pass (GREEN)
3. Run the full test suite to check for regressions
4. Refactor if needed while keeping tests green

### Mocking Discipline
- No mocking needed — this is a pure function with no I/O, no network, no DB.
- All tests use real inputs and assert on real outputs.

## Acceptance Criteria
- [ ] `simulate_looping(...)` returns dict with all 9 output keys (+ calc_version)
- [ ] Deposit APY 5%, Borrow APY 2% with leverage → net_apy > 5% (positive leverage amplification)
- [ ] Deposit APY == Borrow APY → net_apy == deposit_apy (no benefit)
- [ ] Borrow APY > Deposit APY → net_apy < deposit_apy (negative carry detected)
- [ ] Max loops enforced — function terminates even with tiny LTV step
- [ ] Safety buffer respected — stops before hitting raw target_ltv
- [ ] Zero capital handled without division by zero
- [ ] Deterministic: same inputs → same outputs
- [ ] `calc_version` == `"loop-v1"` in return dict
- [ ] All 9 tests pass: `pytest tests/test_looping.py -v`
- [ ] Full test suite still passes after implementation
