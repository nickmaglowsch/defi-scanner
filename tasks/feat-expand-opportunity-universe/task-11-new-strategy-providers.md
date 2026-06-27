# Task 11 — New Strategy Providers (Stable Lending, Staking, Restaking, Pendle)

## Objective

Add adapters for stable lending, liquid staking, restaking, and Pendle fixed-yield opportunities.

## Context

Planning decision Q8-A implements these as `LendingProvider` variants with distinct `market_type` values. They flow through the existing `LendingCollector` and generic opportunity pipeline.

## Requirements

1. Create `backend/app/collectors/stable_lending.py`:
   - Produces markets with `market_type="lending"` and `deposit_apy` only (no borrow leg).
   - Can reuse existing lending market data but explicitly flags stable-lend strategy.
2. Create `backend/app/collectors/staking.py`:
   - `market_type="staking"`
   - Assets: wstETH, ezETH, rsETH
   - Returns `deposit_apy` (staking yield), `tvl`, `raw_payload`
3. Create `backend/app/collectors/restaking.py`:
   - `market_type="restaking"`
   - EigenLayer ecosystem; returns `deposit_apy`, `tvl`, `raw_payload`
4. Create `backend/app/collectors/pendle.py`:
   - `market_type="pendle"`
   - Returns fixed-yield APY and implied yield; include maturity in `raw_payload`
5. Each adapter accepts an injectable client and reads from the registry.
6. Update `backend/app/calculations/orchestrator.py` to trigger a simple calculation for these market types (or skip loop simulation when there is no borrow leg).
7. Update `backend/app/api/routes.py` to return `OpportunityOut` with `strategy_type` matching `market_type`.
8. Add tests for each adapter.

## Target Files

- `backend/app/collectors/stable_lending.py` (new)
- `backend/app/collectors/staking.py` (new)
- `backend/app/collectors/restaking.py` (new)
- `backend/app/collectors/pendle.py` (new)
- `backend/app/calculations/orchestrator.py`
- `backend/app/api/routes.py`
- `backend/tests/test_stable_lending_adapter.py` (new)
- `backend/tests/test_staking_adapter.py` (new)
- `backend/tests/test_restaking_adapter.py` (new)
- `backend/tests/test_pendle_adapter.py` (new)

## Dependencies

- Task 02 (registry)
- Task 08 (generic `OpportunityOut`)

## TDD Mode

Yes.

- Write mocked adapter tests first.

## Acceptance Criteria

1. All four new adapter test files pass.
2. `/opportunities` can return `strategy_type` values `stable_lending`, `staking`, `restaking`, and `pendle`.
3. Stable lending / staking / restaking / Pendle opportunities do not attempt leveraged-loop simulation.
4. Registry contains entries for these strategy types.

## Notes

- Stable lending can be synthetically derived from existing lending snapshots for assets with no borrow leg, or from a dedicated source.
- Staking yields can come from Lido/Rocket Pool APIs or on-chain `getStETH` exchange rates.
- Restaking yields may require EigenLayer AVS reward data; if unavailable, stub with `NotImplementedError`.
- Pendle data can come from the Pendle API; fixed-yield APY is the primary metric.
