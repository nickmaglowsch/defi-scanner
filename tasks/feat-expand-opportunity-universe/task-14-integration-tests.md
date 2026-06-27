# Task 14 — Integration Tests and Adapter Fixtures

## Objective

Add end-to-end integration tests, shared fixtures, and adapter mocks that verify the expanded scanner pipeline works together.

## Context

With many new adapters and a generic schema, we need tests that exercise the registry, collectors, calculations, and API without relying on live external services.

## Requirements

1. Create `backend/tests/fixtures/` with JSON/HTTP response fixtures for:
   - Aave `getReservesList` / `getReserveData`
   - Morpho, Spark, Euler sample market responses
   - Hyperliquid, GMX, Drift, Vertex, dYdX funding responses
   - Staking/restaking/Pendle sample responses
2. Add `backend/tests/test_registry_loader.py` if not already covered by Task 02.
3. Add `backend/tests/test_collector_integration.py`:
   - Use the mock DB session fixture to run `LendingCollector` and `FundingCollector` with mocked providers.
   - Assert snapshots are written with correct `chain`, `protocol`, and `market_type`.
4. Add `backend/tests/test_api_integration.py`:
   - Seed the mock DB with snapshots from multiple protocols/chains.
   - Call `/api/v1/opportunities` and assert generic `OpportunityOut` fields, strategy types, and percentile/rank fields.
5. Add `backend/tests/test_orchestrator.py`:
   - Assert loop, carry, cross-protocol, and stable calculations are triggered after snapshot writes.
6. Update `backend/tests/conftest.py` with shared fixtures for registry entries and mock providers.
7. Ensure all 168+ existing tests still pass.

## Target Files

- `backend/tests/conftest.py`
- `backend/tests/fixtures/*` (new)
- `backend/tests/test_collector_integration.py` (new)
- `backend/tests/test_api_integration.py` (new)
- `backend/tests/test_orchestrator.py` (new or update)

## Dependencies

- All prior tasks.

## TDD Mode

No.

- Integration tests are written after the components exist; they verify assembly, not drive design.

## Acceptance Criteria

1. Full backend test suite passes: `pytest backend/`.
2. Integration tests cover at least three lending protocols, two funding exchanges, and one cross-protocol opportunity.
3. Tests verify `chain` is populated on `Market` rows.
4. Tests verify `strategy_type` is present in `/opportunities` responses.

## Notes

- Use the existing `mock_db_session_factory` fixture pattern.
- Keep fixtures minimal; one representative market per protocol is enough for integration coverage.
- If a protocol adapter is stubbed with `NotImplementedError`, skip its integration test with a clear reason.
