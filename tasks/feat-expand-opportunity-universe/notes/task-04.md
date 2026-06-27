# Task 04 — Lending Adapters Batch 1 (Morpho, Spark, Euler)

## What changed

- Added `backend/app/collectors/morpho.py` — Morpho Blue adapter using the public GraphQL API.
- Added `backend/app/collectors/spark.py` — SparkLend adapter that subclasses `AaveV3Adapter` (Spark is an Aave V3 fork).
- Added `backend/app/collectors/euler.py` — Euler V2 adapter using the Euler V3 API preview.
- Added mocked tests for each adapter:
  - `backend/tests/test_morpho_adapter.py`
  - `backend/tests/test_spark_adapter.py`
  - `backend/tests/test_euler_adapter.py`
- Updated `backend/app/protocols/registry.yaml` with real data-source endpoints/addresses for Morpho, Spark, and Euler.

## Data sources

| Protocol | Source | Endpoint |
|----------|--------|----------|
| Morpho | GraphQL | `https://api.morpho.org/graphql` |
| Spark | Ethereum RPC | Pool `0xC13e21B648A5Ee794902342038FF3aDAB66BE987` |
| Euler | REST | `https://v3.euler.finance/v3` |

## Implementation notes

- Each adapter accepts a `RegistryEntry` and an injectable HTTP/Web3 client for tests.
- Returned dicts include all required normalized fields:
  `asset`, `deposit_apy`, `borrow_apy`, `utilization`, `available_liquidity`,
  `total_supplied`, `total_borrowed`, `tvl`, `ltv_pct`,
  `liquidation_threshold_pct`, `reserve_factor_pct`, `reward_apy`, `chain`,
  `protocol`, `market_type`, `raw_payload`.
- Morpho:
  - Queries `markets` filtered by `chainId_in` and `loanAssetAddress_in`.
  - One result per market; `asset` is formatted as `{loan}/{collateral}`.
  - `lltv` is used for both `ltv_pct` and `liquidation_threshold_pct`.
  - `reward_apy` is set to `0.0` because the endpoint does not expose rewards.
- Spark:
  - Reuses Aave V3 ABI helpers and the on-chain `getReserveData` path.
  - `SparkAdapter` is a thin wrapper around `AaveV3Adapter` that passes the registry entry.
- Euler:
  - Paginates `/evk/vaults` using the returned vault count.
  - Filters results to the symbols listed in the registry entry.
  - Risk parameters (`ltv_pct`, `liquidation_threshold_pct`, `reserve_factor_pct`) are not
    returned by the list endpoint and are currently `0.0`; upgrade to per-vault config
    endpoints if needed.
  - `reward_apy` is set to `0.0` because the list endpoint does not expose rewards.

## Test results

```
pytest backend/tests/test_morpho_adapter.py backend/tests/test_spark_adapter.py backend/tests/test_euler_adapter.py -q
21 passed

pytest backend/tests -q
236 passed
```

## Blockers

None. All three protocols have reliable public data sources and the adapters pass tests.
