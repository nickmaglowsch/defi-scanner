"""EigenLayer restaking adapter.

market_type = "restaking"; no borrow leg, no loop simulation.

# ponytail: EigenLayer AVS reward data is not available via a stable public REST API
# as of 2026. On-chain reads require RPC access to the StrategyManager contract and
# AVS reward distributors. Stub raises NotImplementedError until a reliable source
# is identified.
"""

from __future__ import annotations

import httpx

from app.protocols.registry import RegistryEntry


class RestakingAdapter:
    """EigenLayer restaking data adapter.

    Raises NotImplementedError — EigenLayer AVS reward data unavailable via
    public REST. Upgrade path: read from EigenLayer contracts via RPC once
    an AVS reward distributor API is confirmed stable.
    """

    def __init__(
        self,
        entry: RegistryEntry,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.entry = entry
        self._client = client

    async def fetch_reserves(self) -> list[dict[str, object]]:
        """Fetch restaking yields.

        # ponytail: EigenLayer AVS reward data has no stable public REST API (2026).
        # On-chain alternative: StrategyManager.getDeposits() + AVS RewardsCoordinator.
        # Implement when RPC provider and AVS registry are confirmed.
        """
        raise NotImplementedError(
            "ponytail: EigenLayer AVS reward data unavailable via public REST API. "
            "Upgrade path: RPC reads from EigenLayer StrategyManager + RewardsCoordinator "
            "contracts when an RPC provider is configured for restaking strategies."
        )
