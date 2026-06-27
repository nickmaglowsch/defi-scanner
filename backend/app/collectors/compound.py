"""Compound V3 (Comet) adapter.

Compound V3 uses isolated Comet contracts (one per market) on-chain.
The legacy V2 REST API was shut down April 2023, and no official public
REST API exists for V3 as of 2026. COMP reward data is also only available
via on-chain reads from the CometRewards contract.

# ponytail: no reliable public Compound V3 REST API found; requires RPC
# integration against Comet contracts + CometRewards for reward_apy.
# Implement when an RPC provider is wired in (see: task for RPC collector layer).
"""

from __future__ import annotations

import httpx

from app.protocols.registry import RegistryEntry


class CompoundAdapter:
    """Placeholder for Compound V3 (Comet) lending adapter.

    Raises NotImplementedError until a reliable public data source is available.
    """

    def __init__(
        self,
        entry: RegistryEntry,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.entry = entry
        self._client = client

    async def fetch_reserves(self) -> list[dict[str, object]]:
        # ponytail: Compound V3 has no public REST API; V2 API shut down April 2023.
        # RPC integration needed: read Comet.getAssetInfo() + CometRewards for reward_apy.
        raise NotImplementedError(
            "ponytail: Compound V3 REST API unavailable; "
            "implement via RPC reads against Comet contracts when provider is wired in"
        )
