# Task 02 — Protocol Registry Config + Loader

## Objective

Create a committed YAML registry of protocols, chains, assets, and contract addresses, plus a Python loader that adapters and collectors consume.

## Context

Planning decision Q2-B replaces scattered env vars with a static registry file. This task establishes the format and loader so later adapter tasks have a single source of truth.

## Requirements

1. Create `backend/app/protocols/registry.yaml` containing entries for every in-scope protocol/chain combination with:
   - `protocol` display name and slug
   - `type`: `lending`, `derivatives`, `staking`, `restaking`, or `pendle`
   - `chain`
   - `data_source` (e.g. `rpc`, `subgraph`, `rest`)
   - `pool_address` or equivalent contract/endpoint identifier
   - `assets` map: symbol -> address
   - Optional `rpc_url` override per chain
2. Create `backend/app/protocols/registry.py` with:
   - `load_registry()` returning a typed dataclass/list structure
   - `get_protocol_entries(protocol: str, chain: str | None = None)` helper
   - Validation that every entry has required fields
3. Add a settings field or env var `DEFI_PROTOCOL_REGISTRY_PATH` defaulting to the committed file path.
4. Add unit tests for the loader:
   - Registry parses without errors
   - Missing required fields raise a clear validation error
   - Filter helpers return expected entries

## Target Files

- `backend/app/protocols/registry.yaml` (new)
- `backend/app/protocols/registry.py` (new)
- `backend/app/protocols/__init__.py` (new)
- `backend/app/config.py`
- `backend/tests/test_protocol_registry.py` (new)

## Dependencies

None.

## TDD Mode

Yes.

- Write tests for `load_registry()` and `get_protocol_entries()` against a temporary YAML fixture before implementing the loader.

## Acceptance Criteria

1. `pytest backend/tests/test_protocol_registry.py` passes.
2. `load_registry()` returns entries for Aave V3, Morpho, Spark, Euler, Fluid, Moonwell, Compound, Silo, Hyperliquid, GMX, Drift, Vertex, and dYdX.
3. Every entry has `protocol`, `type`, `chain`, `data_source`, and `assets`.
4. Validation rejects malformed entries with a clear message.

## Notes

- The registry does not need to contain live contract addresses for every chain at this stage; placeholders with a `ponytail:` comment are acceptable for protocols where research is pending, but the shape must be real.
- Keep the registry human-editable; avoid deeply nested structures.
