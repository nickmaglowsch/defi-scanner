# Task 05 — New Lending Adapters Batch 2 (Fluid, Moonwell, Compound, Silo)

## Objective

Implement `LendingProvider` adapters for Fluid, Moonwell, Compound, and Silo.

## Context

Second batch of lending protocols. These share the same normalized interface established in Task 04.

## Requirements

1. Create `backend/app/collectors/fluid.py`, `backend/app/collectors/moonwell.py`, `backend/app/collectors/compound.py`, and `backend/app/collectors/silo.py` implementing `fetch_reserves()` with the normalized dict contract.
2. Each adapter accepts an injectable client and reads configuration from the registry.
3. Compound must report `reward_apy` if COMP reward data is available from the chosen source.
4. Silo markets are isolated per collateral asset; ensure the adapter returns one reserve dict per isolated market and names the asset clearly.
5. If a reliable public data source cannot be identified, raise `NotImplementedError` with a `ponytail:` comment.
6. Add tests for each adapter using mocked clients.

## Target Files

- `backend/app/collectors/fluid.py` (new)
- `backend/app/collectors/moonwell.py` (new)
- `backend/app/collectors/compound.py` (new)
- `backend/app/collectors/silo.py` (new)
- `backend/tests/test_fluid_adapter.py` (new)
- `backend/tests/test_moonwell_adapter.py` (new)
- `backend/tests/test_compound_adapter.py` (new)
- `backend/tests/test_silo_adapter.py` (new)

## Dependencies

- Task 02 (registry)
- Task 04 (pattern established)

## TDD Mode

Yes.

- Write mocked tests first, then implement each adapter.

## Acceptance Criteria

1. All four adapter test files pass.
2. Each adapter returns normalized reserve dicts.
3. Compound adapter exposes `reward_apy` when available.
4. Silo adapter returns one entry per isolated market.

## Notes

- Fluid (fTokens) may require reading multiple vault-like contracts; prefer a single aggregator if available.
- Moonwell is Moonbeam/Base-based; Base RPC may be needed.
- Compound V3 uses `cToken` / `Comet` patterns.
- Silo isolated markets mean the same debt asset can appear multiple times with different collateral; include collateral symbol in the returned asset name if needed (e.g. `USDC-ETH`).
