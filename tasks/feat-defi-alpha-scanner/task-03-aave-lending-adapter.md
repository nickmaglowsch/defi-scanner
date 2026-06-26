# Task 03: Aave V3 Lending Adapter & Collector

## Objective
Define the `LendingProvider` protocol interface, implement the Aave V3 on-chain adapter via web3.py, and build the lending collector service that writes snapshots to the database on a schedule.

## Context
This is the first concrete data ingestion path. The Aave adapter reads on-chain data from the Aave V3 Pool contract on Ethereum mainnet. The design must:
- Abstract the data source behind a `LendingProvider` protocol (Python `Protocol` or ABC) so Morpho/Spark can be added later by implementing the same interface.
- Embed a minimal ABI JSON for only the `getReserveData` function (and ERC20 `totalSupply` for aToken/variableDebtToken).
- Convert RAY (1e27) values to percentage APY.
- Read per-asset reserve data + token supplies to compute deposit APY, borrow APY, utilization, available liquidity, total supplied, total borrowed, TVL.

See `updated-prd.md` Sections "Aave V3 on-chain via web3.py" (Decisions Log Q4) and "Collectors" for design.

**Quick Context**:
- Config via `app.config.Settings` (RPC_URL, collector interval).
- Models from task-02: `Protocol`, `Market`, `LendingSnapshot`.
- DB session via `get_db()` async generator from task-01.
- Aave V3 Pool proxy: `0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2` (hardcode as default, override via env).
- Assets: USDC `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`, USDT `0xdAC17F958D2ee523a2206206994597C13D831ec7`, DAI `0x6B175474E89094C44Da98b954EedeAC495271d0F`, WETH `0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2`, wstETH `0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0`.

## Target Files
- `backend/app/collectors/__init__.py`
- `backend/app/collectors/base.py`
- `backend/app/collectors/aave.py`
- `backend/app/collectors/lending.py`
- `backend/tests/__init__.py`
- `backend/tests/conftest.py`
- `backend/tests/test_aave_adapter.py`

## Dependencies
- task-02 (needs models + DB session)

## Steps
1. Write `backend/app/collectors/base.py`:
   - Define `LendingProvider` as a `Protocol` with async method: `async def fetch_reserves(self) -> list[dict]` — returns list of dicts with keys matching `LendingSnapshot` fields (asset, deposit_apy, borrow_apy, utilization, etc.).
   - Define `FundingProvider` protocol (placeholder — implemented in task-04) with `async def fetch_funding_rates(self) -> list[dict]`.
2. Write `backend/app/collectors/aave.py`:
   - Class `AaveV3Adapter` implementing `LendingProvider`.
   - `__init__` takes `rpc_url`, `pool_address`, `assets` dict (symbol → token address).
   - On init: create `web3.Web3(Web3.HTTPProvider(rpc_url))`, load Aave V3 Pool contract from embedded minimal ABI.
   - Embed minimal ABI as a module-level constant (`_AAVE_POOL_ABI`) — only `getReserveData(address)` → tuple, `getReservesList()` → address[]. Also embed ERC20 `totalSupply()` ABI fragment.
   - `async fetch_reserves()`:
     - Run sync web3 calls in `asyncio.to_thread()` (web3.py is sync; thread pool avoids blocking).
     - Call `contract.functions.getReservesList().call()` → list of asset addresses.
     - For each asset in our tracked set: call `contract.functions.getReserveData(asset_address).call()` → tuple with fields: `(configuration, liquidityIndex, currentLiquidityRate, currentVariableBorrowRate, currentStableBorrowRate, lastUpdateTimestamp, aTokenAddress, stableDebtTokenAddress, variableDebtTokenAddress, ...)`. Map to `ReserveData` namedtuple/dataclass.
     - Parse `configuration.data` bits for LTV (bits 16-31, div 100 = %), liquidation threshold (bits 32-47), reserve factor (bits 0-15).
     - Convert RAY rates: `apy = rate / 1e27 * 100`.
     - Read aToken `totalSupply()` → total supplied, variableDebtToken `totalSupply()` → total borrowed.
     - Compute: utilization = total_borrowed / total_supplied (guard div-by-zero), available_liquidity = total_supplied - total_borrowed, TVL = total_supplied (or use available_liquidity — note definition).
     - Return list of dicts, one per asset.
   - Retry wrapper: `_retry_call(func, max_retries=3, backoff=(1,2,4))` — catches exceptions, logs, re-raises on exhaustion.
   - Configurable via `app.config.Settings` (RPC_URL). Pool address and assets configurable via env with defaults.
3. Write `backend/app/collectors/lending.py`:
   - `LendingCollector` service class:
     - Takes async DB session factory, `LendingProvider` instance.
     - `async collect()`: calls `provider.fetch_reserves()`, upserts `Protocol` row (name="Aave V3"), upserts `Market` rows (one per asset), inserts `LendingSnapshot` rows with all fields + `raw_payload` = JSON dump of the raw on-chain response.
     - Upsert logic: `INSERT ... ON CONFLICT (unique_key) DO NOTHING` or use SQLAlchemy `merge`.
     - Log snapshot count and any errors.
   - Expose as a callable for the scheduler.
4. Wire collector into `backend/app/main.py`:
   - In `lifespan` (or `startup` event): create `AaveV3Adapter` + `LendingCollector`, spawn `asyncio.create_task(_run_collector_loop(collector, interval))` where `_run_collector_loop` sleeps `COLLECTOR_INTERVAL_SECONDS` between cycles. Graceful shutdown via an `asyncio.Event`.
   - This is a ponytail scheduler — no extra dependency. Add comment noting upgrade path to APScheduler if needed.
5. Write `backend/tests/conftest.py`:
   - `@pytest.fixture` for a test DB (use SQLite in-memory or skip if asyncpg required — use `pytest-asyncio` with a test database fixture that creates/drops tables per test). Document how to run tests (needs Docker timescaledb or a test override).
   - `@pytest.fixture` for mock web3: returns a `MagicMock` with `eth.contract.return_value.functions.getReserveData.return_value.call.return_value = (config, liq_index, liq_rate, var_borrow_rate, stable_borrow_rate, ts, a_token_addr, stable_debt_addr, var_debt_addr, ...)` pre-configured.
6. Write `backend/tests/test_aave_adapter.py`:
   - Test RAY → APY conversion: `1e27 * 0.05` (5% in RAY) → 5.0%.
   - Test `fetch_reserves()` with mocked web3: returns correct list of dicts with expected keys.
   - Test retry: mock fails twice, succeeds third time — call count = 3.
   - Test retry exhaustion: mock fails 3 times → raises, log contains error.
   - Test utilization calculation: total_borrowed / total_supplied.
   - Test adapter handles empty reserve list gracefully.

## Acceptance Criteria
- [ ] `AaveV3Adapter.fetch_reserves()` returns one dict per tracked asset with all expected numeric fields
- [ ] RAY conversion correct: `rate / 1e27 * 100 == APY %`
- [ ] Retry with exponential backoff works: 3 attempts on failure, succeeds if 3rd works
- [ ] Retry exhaustion logs error and skip — does not crash the application
- [ ] `LendingCollector.collect()` writes `Protocol`, `Market`, and `LendingSnapshot` rows to DB
- [ ] `raw_payload` column contains the full on-chain response as JSON
- [ ] Subsequent collect cycles do not duplicate protocol/market rows (upsert behavior)
- [ ] All unit tests pass: `pytest tests/test_aave_adapter.py -v`
- [ ] Collector loop starts on app startup (visible in logs) with configurable interval
- [ ] `ruff check` passes on all new files
