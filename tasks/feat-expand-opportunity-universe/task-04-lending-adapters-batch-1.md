# Task 04 — New Lending Adapters Batch 1 (Morpho, Spark, Euler)

## Objective

Implement `LendingProvider` adapters for Morpho, Spark, and Euler using the registry and normalized return contract.

## Context

Planning decision Q2-B and Q5-B require every new protocol to expose the same normalized interface. This task covers the first batch of lending protocols.

## Requirements

1. Create `backend/app/collectors/morpho.py` implementing `fetch_reserves()` returning normalized dicts with all required fields:
   - `asset`, `deposit_apy`, `borrow_apy`, `utilization`, `available_liquidity`, `total_supplied`, `total_borrowed`, `tvl`, `ltv_pct`, `liquidation_threshold_pct`, `reserve_factor_pct`, `reward_apy`, `chain`, `protocol`, `market_type`, `raw_payload`
2. Create `backend/app/collectors/spark.py` with the same contract.
3. Create `backend/app/collectors/euler.py` with the same contract.
4. Each adapter must accept an injectable HTTP/Web3 client for tests.
5. Each adapter reads its configuration from a registry entry (see Task 02).
6. If a reliable public data source cannot be identified for a protocol, raise `NotImplementedError` with a `ponytail:` comment explaining the blocker — do not ship fake data.
7. Add tests for each adapter using mocked clients.

## Target Files

- `backend/app/collectors/morpho.py` (new)
- `backend/app/collectors/spark.py` (new)
- `backend/app/collectors/euler.py` (new)
- `backend/tests/test_morpho_adapter.py` (new)
- `backend/tests/test_spark_adapter.py` (new)
- `backend/tests/test_euler_adapter.py` (new)

## Dependencies

- Task 02 (registry)

## TDD Mode

Yes.

- For each adapter, write a test that mocks the data source and asserts the returned dict shape and values before implementing the adapter body.

## Acceptance Criteria

1. `pytest backend/tests/test_morpho_adapter.py backend/tests/test_spark_adapter.py backend/tests/test_euler_adapter.py` passes.
2. Each adapter returns dicts matching the normalized contract.
3. Each adapter is importable and instantiable with a registry entry.

## Notes

- Morpho often exposes markets via subgraph or API; prefer the simplest reliable source.
- Spark is an Aave V3 fork on Ethereum/Gnosis; on-chain reads may reuse Aave ABI patterns.
- Euler uses its own modular lending architecture; document the chosen data source in a `ponytail:` comment.
