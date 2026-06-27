# Task 03 — Refactor Aave Adapter for Registry + Multi-Chain

## Objective

Rewrite the Aave V3 adapter to source its configuration from the registry and return chain-aware reserve data.

## Context

The existing `AaveV3Adapter` hardcodes Ethereum mainnet assets via env vars. Planning decisions Q1-B (chain on Market) and Q2-B (registry) require the adapter to accept a registry entry and return reserves tagged with the chain.

## Requirements

1. Refactor `app/collectors/aave.py`:
   - `AaveV3Adapter.__init__(self, registry_entry, rpc_url, client=None)` where `registry_entry` is a registry dataclass.
   - Accept an optional injectable `Web3` client for tests.
   - Each returned reserve dict must include `chain`, `protocol`, and `market_type="lending"`.
   - Include `reward_apy` (default `None`) in returned dict.
2. Ensure raw payload still includes `ltv_pct`, `liquidation_threshold_pct`, `reserve_factor_pct`.
3. Update `app/collectors/lending.py` to pass `chain` through `_upsert_market` and `protocol`/`chain` through `_upsert_protocol`.
4. Update `app/collectors/__init__.py` to instantiate Aave from the registry instead of parsing `AAVE_ASSETS`.
5. Keep `AAVE_POOL_ADDRESS` and `AAVE_ASSETS` env vars as fallbacks for backward compatibility during transition.
6. Add/update tests in `backend/tests/test_aave_adapter.py` using an injected mock Web3 client.

## Target Files

- `backend/app/collectors/aave.py`
- `backend/app/collectors/lending.py`
- `backend/app/collectors/__init__.py`
- `backend/app/config.py` (fallback behavior only)
- `backend/tests/test_aave_adapter.py`

## Dependencies

- Task 01 (schema `chain` column)
- Task 02 (registry loader)

## TDD Mode

Yes.

- Write adapter tests with a mock Web3 that returns fixed `getReservesList` / `getReserveData` / `totalSupply` responses.
- Verify returned reserve dicts include chain, protocol, and required fields.

## Acceptance Criteria

1. `pytest backend/tests/test_aave_adapter.py` passes.
2. `AaveV3Adapter` no longer parses `AAVE_ASSETS` directly.
3. Lending snapshots from Aave include the correct `chain` on the `Market` row.
4. Existing API tests still pass.

## Notes

- The registry entry for Aave V3 will contain one entry per chain (Ethereum, Base, Arbitrum, Optimism, Polygon).
- `reward_apy` is `None` for Aave unless reward data is available; the field is optional.
