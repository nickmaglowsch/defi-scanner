# Task 06 — New Funding Adapters (GMX, Drift, Vertex, dYdX)

## Objective

Implement `FundingProvider` adapters for GMX, Drift, Vertex, and dYdX, normalizing funding rates to the existing contract.

## Context

Planning decision Q4-B requires each funding adapter to normalize its own data. This task expands funding coverage beyond Hyperliquid.

## Requirements

1. Create `backend/app/collectors/gmx.py`, `backend/app/collectors/drift.py`, `backend/app/collectors/vertex.py`, and `backend/app/collectors/dydx.py` implementing `fetch_funding_rates()`.
2. Each adapter returns a list of dicts with keys:
   - `asset`, `funding_rate`, `funding_interval_hours`, `annualized_funding`, `open_interest`, `volume_24h`, `long_short_ratio`, `mark_price`, `index_price`, `raw_payload`, plus `chain`, `protocol`, `market_type="perp"`
3. Each adapter accepts an injectable HTTP client.
4. Funding interval and annualization math must be specific to each exchange and documented in a `ponytail:` comment.
5. If an exchange does not expose long-short OI, default `long_short_ratio` to `1.0` with a comment.
6. Add mocked tests for each adapter.

## Target Files

- `backend/app/collectors/gmx.py` (new)
- `backend/app/collectors/drift.py` (new)
- `backend/app/collectors/vertex.py` (new)
- `backend/app/collectors/dydx.py` (new)
- `backend/tests/test_gmx_adapter.py` (new)
- `backend/tests/test_drift_adapter.py` (new)
- `backend/tests/test_vertex_adapter.py` (new)
- `backend/tests/test_dydx_adapter.py` (new)

## Dependencies

- Task 02 (registry)

## TDD Mode

Yes.

- Write tests with mocked REST responses first; verify annualization math and key extraction.

## Acceptance Criteria

1. All four funding adapter test files pass.
2. Each adapter returns normalized funding dicts.
3. Annualized funding values are correct given mocked input.
4. Adapters are importable and instantiable with a registry entry.

## Notes

- GMX V1 funds hourly; GMX V2 has 1-hour pools on Arbitrum/Avalanche.
- Drift is Solana-based; its API returns funding rates that need conversion.
- Vertex is cross-margin; funding may be asset-specific.
- dYdX v4 uses a Cosmos appchain with a public API.
