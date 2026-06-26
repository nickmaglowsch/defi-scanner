"""Provider protocols — abstract data-source interfaces for collectors.

New adapters (Morpho, Spark, Hyperliquid) implement these protocols
so collectors can remain source-agnostic.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LendingProvider(Protocol):
    """Protocol for any lending protocol data adapter.

    Implementations must return a list of dicts per asset with keys
    matching LendingSnapshot fields: asset, deposit_apy, borrow_apy,
    utilization, available_liquidity, total_supplied, total_borrowed,
    tvl, plus optional raw field for raw_payload.
    """

    async def fetch_reserves(self) -> list[dict[str, object]]: ...


@runtime_checkable
class FundingProvider(Protocol):
    """Protocol for any perpetuals/funding-rate data adapter (task-04)."""

    async def fetch_funding_rates(self) -> list[dict[str, object]]: ...
