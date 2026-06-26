---
name: asyncpg-event-loop-fixture
description: asyncpg engine must be created inside pytest fixture, not at module level, to avoid "attached to a different loop" errors
metadata:
  type: feedback
---

asyncpg requires the `create_async_engine()` call to happen on the same event loop as the test. Creating the engine at module level (import time) binds it to the import-time loop, causing `RuntimeError: Task got Future attached to a different loop` when tests run.

**Why:** asyncpg connections are tied to the event loop that created them. pytest-asyncio creates a new loop per test (in function scope), so module-level engines are on the wrong loop.

**How to apply:** Always create `create_async_engine(...)` inside the `@pytest_asyncio.fixture` body, not as a module-level constant. Call `await engine.dispose()` in fixture teardown.
