"""Liquid staking adapter — wstETH, ezETH, rsETH yields.

market_type = "staking"; no borrow leg, no loop simulation.

# ponytail: Lido/Rocket Pool public APIs exist (api.lido.fi/v1/protocol/eth/apr/sma)
# but require HTTP network access. Stub raises NotImplementedError until an HTTP
# client fixture/integration test is wired in. Upgrade path: inject httpx.AsyncClient
# and hit api.lido.fi for Lido; rocketpool.net/api for Rocket Pool.
"""

from __future__ import annotations

import httpx

from app.protocols.registry import RegistryEntry

# Lido public APR endpoint (no auth required).
_LIDO_APR_URL = "https://eth-api.lido.fi/v1/protocol/eth/apr/last_week"


class StakingAdapter:
    """Liquid staking data adapter (Lido, Rocket Pool, etc.).

    Raises NotImplementedError until HTTP network access is wired in.
    market_type is 'staking'; borrow_apy is always None.
    """

    def __init__(
        self,
        entry: RegistryEntry,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.entry = entry
        self._client = client

    async def fetch_reserves(self) -> list[dict[str, object]]:
        """Fetch staking yields for this protocol.

        # ponytail: HTTP fetch not wired in; Lido APR API at api.lido.fi requires
        # live network access which integration tests don't have. Implement when
        # HTTP client with retry + timeout is injected from the collector runner.
        # Upgrade: client.get(_LIDO_APR_URL) → parse {"data": {"smaApr": float}}.
        """
        raise NotImplementedError(
            "ponytail: StakingAdapter HTTP fetch not yet wired in. "
            "Lido APR: GET eth-api.lido.fi/v1/protocol/eth/apr/last_week. "
            "Implement when HTTP client is injected from the collector runner."
        )
