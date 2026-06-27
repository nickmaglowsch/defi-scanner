"""Spark adapter — reads SparkLend reserve data via web3.py.

SparkLend is an Aave V3 fork, so this adapter reuses the Aave ABI fragments
and normalizes the results with the same contract layout.
"""

from __future__ import annotations

from web3 import Web3

from app.collectors.aave import AaveV3Adapter
from app.config import settings
from app.protocols.registry import RegistryEntry


class SparkAdapter(AaveV3Adapter):
    """Reads SparkLend lending reserve data from a registry entry.

    Accepts an injectable Web3 instance for tests; otherwise builds one from
    the registry entry's rpc_url (falling back to settings.RPC_URL).
    """

    def __init__(self, entry: RegistryEntry, w3: Web3 | None = None) -> None:
        rpc_url = entry.rpc_url or settings.RPC_URL
        super().__init__(registry_entry=entry, rpc_url=rpc_url, client=w3)
