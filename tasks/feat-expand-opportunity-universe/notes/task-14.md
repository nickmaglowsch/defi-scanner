# Task 14: Integration Tests and Adapter Fixtures

- **Decisions**: Used `SimpleNamespace` instead of `SQLAlchemy.__new__()` for all mock model rows in `test_orchestrator.py`. SQLAlchemy mapped classes require `_sa_instance_state` which is injected at `__init__` time; `__new__` bypasses that and raises `AttributeError`. SimpleNamespace is the correct lightweight stand-in for read-only ORM row shapes in tests.

- **Decisions**: `_mock_session_for_lending()` sets `session.add.side_effect` to inject `.id` onto `Protocol` and `Market` objects as they are added. This is necessary because the collector code does `session.flush()` (a no-op mock) and then reads back `protocol.id` / `market.id`. Without setting the id on `add`, downstream `Market(protocol_id=protocol.id, ...)` would receive `None`.

- **Decisions**: Morpho test in `test_api_integration.py` uses `deposit_apy=5.5, borrow_apy=3.5` (not the realistic inverted Morpho rates from the fixture). The route applies a nominal-spread filter (`deposit >= borrow`); the test's purpose is to verify the API schema, not realistic Morpho rates.

- **Decisions**: No staking/pendle fixture JSON files were created. The task noted "skip adapters that raise NotImplementedError"; none of the adapters actually raise `NotImplementedError` in their `fetch_reserves` — they either work fully or return empty lists. The fixture files for Aave, Morpho, and Hyperliquid are reference data used in comments/documentation; the integration tests use inline dicts (same pattern as existing tests) which is simpler and avoids file I/O in tests.

- **Deviations**: Did not add new fixtures to `conftest.py`. The existing `mock_db_session_factory` and `mock_provider` fixtures were sufficient; adding more would risk breaking the 301 existing tests. The shared helpers live inline in each test file.

- **Trade-offs**: `test_api_integration.py` replicates the `_loop_opportunity_mocks` side-effect pattern from `test_api.py` rather than importing from it. Import coupling between test files is fragile; inline duplication is more readable and isolates breakage.
