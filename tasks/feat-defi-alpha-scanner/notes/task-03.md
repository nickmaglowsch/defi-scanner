# Task 03: Aave V3 Lending Adapter & Collector

- **Decisions**:
  - APY stored as percentage (e.g., 5.0 = 5%). This matches the PRD's dashboard display expectation.
  - Token amounts stored as raw smallest-unit values (wei for ETH, 6-decimal for USDC). No normalisation applied — the ratio math (utilization) is correct regardless of decimals, and raw values allow the dashboard to format at the display layer.
  - Configuration bit parsing follows the task spec exactly (LTV bits 16-31, liquidation threshold 32-47, reserve factor 0-15, ÷100). These values are included in raw_payload but not in separate snapshot columns (no schema columns exist for them).
  - Collector upsert uses SELECT-then-INSERT rather than ON CONFLICT to avoid aborting the entire batch on unique violations. This is slightly less efficient but tolerant of concurrent writers.
  - `raw_payload` stores string representations for large integers (uint256/uint128) to ensure JSONB compatibility. Hex for configuration.data, decimal strings for rates and token supplies.
- **Deviations**: None. All required tests pass, all acceptance criteria met.
- **Trade-offs**:
  - Token supply fetching is sequential (aToken then debtToken) rather than parallel. Two sequential RPC calls per asset. Switched to gather() if latency becomes an issue — the retry wrapper already handles individual failures.
  - Web3 constructor mocking required patching `Web3.__init__` (rather than the class-level `Web3` mock) because web3 internally does `isinstance(parent_module, Web3)` checks that fail on MagicMock instances. The `_fake_init` sets `self_w3.eth` so subsequent `self.w3.eth.contract()` calls resolve.
  - Async session mocking uses a real `_FakeSessionCtx` class rather than MagicMock's `__aenter__` because Python's `async with` resolves `__aenter__` on the type, not the instance — instance-level AsyncMock assignment is silently ignored.
- **Risks**:
  - The `_AAVE_POOL_ABI` is hand-crafted minimal ABI. If Aave V3 upgrades its Pool interface, the embedded ABI may need updating. The `getReserveData` function signature is stable but not guaranteed forever.
  - The `getReservesList()` call fetches ALL Aave reserves (100+ assets), then filters to tracked. This is a single RPC call so overhead is negligible, but the full list may grow over time.
