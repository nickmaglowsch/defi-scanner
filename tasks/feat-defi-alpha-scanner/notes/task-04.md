# Task 04: Hyperliquid Funding Adapter & Collector

- **Decisions**:
  - HTTP retry uses `httpx.HTTPStatusError` + `asyncio.sleep` instead of building a dedicated retry utility. Matches the inline retry pattern in the Aave adapter (which uses `asyncio.to_thread` for sync web3 calls), adapted for async httpx.
  - `long_short_ratio` hardcoded to `1.0` with a `ponytail:` comment — Hyperliquid's `/info` endpoint doesn't expose directional open interest. Ratio needs a separate data source.
  - Adapter accepts an optional `httpx.AsyncClient` for dependency injection, enabling clean test mocking without `respx`.
  - `raw_payload` stores only the per-market asset context dict (not the full API response), which is what the snapshot row represents. The full raw response can be recreated from the union of individual `raw_payload` fields if needed.
- **Deviations**: None. Config `HYPERLIQUID_API_URL` was already present in `config.py` — no config change needed.
- **Trade-offs**: Skipped `respx` as a test dependency since `pytest-mock` + `AsyncMock` on the injected client achieves the same with zero deps. If more complex HTTP mocking is needed later, add `respx` then.
- **Risks**: Hyperliquid API response shape is validated leniently (checks list-of-2, dict keys). If the API pivots to a different envelope, the adapter returns `[]` with a warning log rather than crashing — safe, but may silently skip cycles. Monitor collector logs on deploy.
