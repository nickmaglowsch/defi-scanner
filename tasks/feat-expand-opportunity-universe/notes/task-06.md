# Task 06 — New Funding Adapters (GMX, Drift, Vertex, dYdX)

## Implemented

- `backend/app/collectors/dydx.py`
  - Full `DydxAdapter` implementation against dYdX v4 public indexer.
  - Endpoint: `GET {DYDX_INDEXER_URL}/v4/perpetualMarkets`.
  - Response normalized to the funding-snapshot contract:
    `asset`, `funding_rate`, `funding_interval_hours`, `annualized_funding`,
    `open_interest`, `volume_24h`, `long_short_ratio`, `mark_price`,
    `index_price`, `raw_payload`, plus `chain="dydx"`, `protocol="dYdX"`,
    `market_type="perp"`.
  - Funding interval: **1 hour** for dYdX v4.
  - Annualization: `rate * 8760 / 1.0`.
  - Skips markets whose `status` is not `ACTIVE`.
  - `long_short_ratio` defaults to `1.0` because the public markets endpoint
    does not expose a long/short OI breakdown.
  - `mark_price` falls back to `oraclePrice` because the endpoint does not
    return a distinct mark price.

- `backend/app/collectors/gmx.py`
  - `GmxAdapter` skeleton with injectable `httpx.AsyncClient`.
  - `fetch_funding_rates()` raises `NotImplementedError`.
  - Reason: GMX v2 does not expose a single reliable public REST endpoint that
    returns funding rates, open interest, and 24h volume. The public token-price
    endpoint only returns oracle prices.

- `backend/app/collectors/drift.py`
  - `DriftAdapter` skeleton with injectable `httpx.AsyncClient`.
  - `fetch_funding_rates()` raises `NotImplementedError`.
  - Reason: Drift funding data lives primarily on-chain on Solana; a stable,
    public REST surface for live perp funding rates is not available.

- `backend/app/collectors/vertex.py`
  - `VertexAdapter` skeleton with injectable `httpx.AsyncClient`.
  - `fetch_funding_rates()` raises `NotImplementedError`.
  - Reason: Vertex's public REST endpoints for live perp funding rates are not
    stable/documented enough for a generic adapter.

- `backend/app/config.py`
  - Added `DYDX_INDEXER_URL` defaulting to `https://indexer.dydx.trade`.

## Tests

- `backend/tests/test_dydx_adapter.py` — 12 mocked tests covering:
  - Annualization math.
  - Normalized key set, asset names, numeric fields, protocol/chain tags.
  - Empty markets, invalid response shapes, inactive-market skipping.

- `backend/tests/test_gmx_adapter.py`
- `backend/tests/test_drift_adapter.py`
- `backend/tests/test_vertex_adapter.py`
  - Each asserts `NotImplementedError` from `fetch_funding_rates()` and verifies
    injectable-client support.

## Test Results

```
backend$ python -m pytest tests/test_dydx_adapter.py tests/test_gmx_adapter.py \
  tests/test_drift_adapter.py tests/test_vertex_adapter.py -v
18 passed
```

Related suites (`test_hyperliquid_adapter.py`, `test_protocol_registry.py`)
also pass.

## Blockers

- GMX, Drift, and Vertex adapters are blocked on confirmed public REST endpoints
  that expose funding rates, open interest, 24h volume, and mark/index prices in
  a single call. Once endpoints are confirmed, the skeletons can be filled in
  following the same normalization pattern used for Hyperliquid and dYdX.
