"""Tests for the registry-driven collector runner (task-07)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.protocols.registry import Registry, RegistryEntry


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_entry(slug: str, type_: str, chain: str = "ethereum") -> RegistryEntry:
    return RegistryEntry(
        protocol=slug.capitalize(),
        slug=slug,
        type=type_,
        chain=chain,
        data_source="rest",
        assets={"USDC": "0x0"},
        pool_address="0x0",
        enabled=True,
    )


def _make_disabled_entry(slug: str, type_: str) -> RegistryEntry:
    return RegistryEntry(
        protocol=slug.capitalize(),
        slug=slug,
        type=type_,
        chain="ethereum",
        data_source="rest",
        assets={"USDC": "0x0"},
        pool_address="0x0",
        enabled=False,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_collectors_schedules_all_enabled_entries() -> None:
    """Both fake adapters' collect() coroutines must be awaited by the runner."""
    fake_lending_entry = _make_entry("fake-lending", "lending")
    fake_derivatives_entry = _make_entry("fake-derivatives", "derivatives")
    fake_registry = Registry(
        version="test",
        entries=[fake_lending_entry, fake_derivatives_entry],
    )

    collect_calls: list[str] = []

    async def lending_collect() -> None:
        collect_calls.append("lending")

    async def funding_collect() -> None:
        collect_calls.append("funding")

    mock_lending_collector = MagicMock()
    mock_lending_collector.collect = lending_collect

    mock_funding_collector = MagicMock()
    mock_funding_collector.collect = funding_collect

    import app.collectors as runner_module

    # Reset module-level state between tests.
    # asyncio.Event is loop-bound; replace with a fresh one for each test loop.
    runner_module._tasks.clear()
    runner_module._shutdown_event = asyncio.Event()

    # Schedule shutdown after one tick so run_collectors doesn't loop forever
    async def _auto_shutdown() -> None:
        await asyncio.sleep(0)
        runner_module._shutdown_event.set()

    with (
        patch.object(runner_module, "load_registry", return_value=fake_registry),
        patch.object(
            runner_module,
            "_build_lending_collector",
            return_value=mock_lending_collector,
        ),
        patch.object(
            runner_module,
            "_build_funding_collector",
            return_value=mock_funding_collector,
        ),
        # Stub out the always-on infrastructure collectors so we only test the
        # registry-driven ones.
        patch.object(runner_module, "_start_infrastructure_tasks"),
    ):
        await asyncio.gather(
            runner_module.run_collectors(),
            _auto_shutdown(),
        )

    assert "lending" in collect_calls, "LendingCollector.collect() was not called"
    assert "funding" in collect_calls, "FundingCollector.collect() was not called"


@pytest.mark.asyncio
async def test_disabled_entries_are_skipped() -> None:
    """Registry entries with enabled=False must not create collector tasks."""
    disabled_entry = _make_disabled_entry("disabled-lending", "lending")
    enabled_entry = _make_entry("real-lending", "lending")
    fake_registry = Registry(
        version="test",
        entries=[disabled_entry, enabled_entry],
    )

    collect_calls: list[str] = []

    async def real_collect() -> None:
        collect_calls.append("real")

    mock_real_collector = MagicMock()
    mock_real_collector.collect = real_collect

    import app.collectors as runner_module

    runner_module._tasks.clear()
    runner_module._shutdown_event = asyncio.Event()

    async def _auto_shutdown() -> None:
        await asyncio.sleep(0)
        runner_module._shutdown_event.set()

    build_calls: list[RegistryEntry] = []

    def _capture_build(entry: RegistryEntry, session_factory: object) -> MagicMock:
        build_calls.append(entry)
        return mock_real_collector

    with (
        patch.object(runner_module, "load_registry", return_value=fake_registry),
        patch.object(
            runner_module,
            "_build_lending_collector",
            side_effect=_capture_build,
        ),
        patch.object(
            runner_module,
            "_build_funding_collector",
            return_value=MagicMock(collect=AsyncMock()),
        ),
        patch.object(runner_module, "_start_infrastructure_tasks"),
    ):
        await asyncio.gather(
            runner_module.run_collectors(),
            _auto_shutdown(),
        )

    built_slugs = [e.slug for e in build_calls]
    assert "disabled-lending" not in built_slugs
    assert "real-lending" in built_slugs


@pytest.mark.asyncio
async def test_shutdown_collectors_cancels_tasks() -> None:
    """shutdown_collectors() must cancel all running tasks cleanly."""
    import app.collectors as runner_module

    runner_module._tasks.clear()
    runner_module._shutdown_event = asyncio.Event()

    # Create a real long-running task so cancel can be observed
    async def _forever() -> None:
        await asyncio.sleep(9999)

    task = asyncio.create_task(_forever())
    runner_module._tasks.append(task)

    await runner_module.shutdown_collectors()

    # Give event loop a tick to propagate cancellation
    await asyncio.sleep(0)
    assert task.cancelled()
