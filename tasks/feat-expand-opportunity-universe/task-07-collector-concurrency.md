# Task 07 — Collector Runner Concurrency Refactor

## Objective

Wire all new lending and funding adapters into the collector runner and run them concurrently.

## Context

Planning decision Q9-A requires adapters to run concurrently while each adapter remains sequential internally. The runner currently hardcodes Aave and Hyperliquid.

## Requirements

1. Refactor `backend/app/collectors/__init__.py`:
   - Load the protocol registry.
   - For every `lending` registry entry, instantiate the appropriate adapter class by protocol slug and create a `LendingCollector` task.
   - For every `derivatives` registry entry, instantiate the appropriate funding adapter and create a `FundingCollector` task.
   - Run all collector tasks concurrently via `asyncio.gather` / `asyncio.create_task`.
   - Maintain graceful shutdown behavior.
2. Add a mapping or registry-driven factory so the runner does not import every adapter unconditionally if its registry entry is marked disabled.
3. Allow registry entries to have `enabled: false` to skip a protocol without code changes.
4. Update tests for the collector runner using mocked collectors.
5. Update `docker-compose.yml` / `run.sh` if new env vars are needed for per-chain RPCs.

## Target Files

- `backend/app/collectors/__init__.py`
- `backend/app/protocols/registry.yaml`
- `backend/app/config.py`
- `backend/tests/test_collector_runner.py` (new or update)
- `docker-compose.yml`
- `run.sh`

## Dependencies

- Task 02 (registry)
- Task 03 (Aave refactor)
- Task 04 (Morpho/Spark/Euler)
- Task 05 (Fluid/Moonwell/Compound/Silo)
- Task 06 (GMX/Drift/Vertex/dYdX)

## TDD Mode

Yes.

- Write a test that mocks the registry with two fake adapters and asserts both `collect()` coroutines are scheduled.
- Implement the runner refactor to satisfy the test.

## Acceptance Criteria

1. `pytest backend/tests/test_collector_runner.py` passes.
2. The runner schedules a task for every enabled registry entry without manual hardcoding.
3. `shutdown_collectors()` cancels all tasks cleanly.
4. Existing startup/shutdown behavior is preserved.

## Notes

- Keep the existing metadata collectors (audit/age) and alert engine wired as before.
- Per-chain RPCs can be supplied via env vars like `DEFI_RPC_URL_BASE`, `DEFI_RPC_URL_ARBITRUM`, etc., falling back to the main `RPC_URL`.
