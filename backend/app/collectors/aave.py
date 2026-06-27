"""Aave V3 on-chain adapter — reads lending reserve data via web3.py."""

from __future__ import annotations

import asyncio
import logging
from collections import namedtuple
from typing import Any

from web3 import Web3
from web3.contract import Contract

from app.protocols.registry import RegistryEntry

logger = logging.getLogger("defi_scanner")

RAY = 10**27

# ── Minimal ABI fragments ──────────────────────────────────────────────────

_AAVE_POOL_ABI: list[dict[str, Any]] = [
    {
        "inputs": [],
        "name": "getReservesList",
        "outputs": [{"internalType": "address[]", "name": "", "type": "address[]"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "asset", "type": "address"}],
        "name": "getReserveData",
        "outputs": [
            # ReserveConfigurationMap is a single-field uint256 struct that
            # ABI-encodes inline as a plain uint256 (no offset word). Declaring
            # it as `uint256` (not a tuple) is what web3/eth_abi can decode.
            # This mirrors the on-chain DataTypes.ReserveDataLegacy struct: `id`
            # is a uint16 sitting BETWEEN lastUpdateTimestamp and the addresses,
            # followed by three trailing uint128s. Field order/count must match
            # exactly or eth_abi reads each slot from the wrong offset.
            {"internalType": "uint256", "name": "configuration", "type": "uint256"},
            {"internalType": "uint128", "name": "liquidityIndex", "type": "uint128"},
            {"internalType": "uint128", "name": "currentLiquidityRate", "type": "uint128"},
            {"internalType": "uint128", "name": "variableBorrowIndex", "type": "uint128"},
            {"internalType": "uint128", "name": "currentVariableBorrowRate", "type": "uint128"},
            {"internalType": "uint128", "name": "currentStableBorrowRate", "type": "uint128"},
            {"internalType": "uint40", "name": "lastUpdateTimestamp", "type": "uint40"},
            {"internalType": "uint16", "name": "id", "type": "uint16"},
            {"internalType": "address", "name": "aTokenAddress", "type": "address"},
            {"internalType": "address", "name": "stableDebtTokenAddress", "type": "address"},
            {"internalType": "address", "name": "variableDebtTokenAddress", "type": "address"},
            {"internalType": "address", "name": "interestRateStrategyAddress", "type": "address"},
            {"internalType": "uint128", "name": "accruedToTreasury", "type": "uint128"},
            {"internalType": "uint128", "name": "unbacked", "type": "uint128"},
            {"internalType": "uint128", "name": "isolationModeTotalDebt", "type": "uint128"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

_ERC20_ABI: list[dict[str, Any]] = [
    {
        "constant": True,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


# ── ReserveData namedtuple ─────────────────────────────────────────────────

_ReserveData = namedtuple(
    "_ReserveData",
    [
        "configuration_data",
        "liquidity_index",
        "liquidity_rate",
        "variable_borrow_index",
        "variable_borrow_rate",
        "stable_borrow_rate",
        "last_update_timestamp",
        "a_token_address",
        "stable_debt_token_address",
        "variable_debt_token_address",
        "interest_rate_strategy_address",
        "reserve_id",
    ],
)


def _ray_to_apy_pct(ray_rate: int) -> float:
    """Convert a RAY (1e27) rate to APY percentage.

    Example: 5e25 (5% in RAY) -> 5.0
    """
    return (ray_rate / RAY) * 100


def _parse_config_data(config_data: int) -> dict[str, float]:
    """Extract LTV, liquidation threshold, and reserve factor from configuration bits.

    Aave V3 ReserveConfiguration layout:
      - Bits 0-15:  reserve factor (÷100 = %)
      - Bits 16-31: LTV (÷100 = %)
      - Bits 32-47: liquidation threshold (÷100 = %)
    """
    return {
        "reserve_factor_pct": ((config_data >> 0) & 0xFFFF) / 100,
        "ltv_pct": ((config_data >> 16) & 0xFFFF) / 100,
        "liquidation_threshold_pct": ((config_data >> 32) & 0xFFFF) / 100,
    }


# ── Adapter ────────────────────────────────────────────────────────────────


class AaveV3Adapter:
    """Reads Aave V3 lending reserve data for a registry entry."""

    def __init__(
        self,
        registry_entry: RegistryEntry,
        rpc_url: str,
        client: Web3 | None = None,
    ) -> None:
        self.registry_entry = registry_entry
        self.chain = registry_entry.chain
        self.protocol = registry_entry.protocol
        self.w3 = client if client is not None else Web3(Web3.HTTPProvider(rpc_url))
        if not registry_entry.pool_address:
            raise ValueError("registry_entry.pool_address is required")
        self.pool_address = Web3.to_checksum_address(registry_entry.pool_address)
        self.pool: Contract = self.w3.eth.contract(address=self.pool_address, abi=_AAVE_POOL_ABI)
        # {symbol: checksummed_address}
        self.assets: dict[str, str] = {
            sym: Web3.to_checksum_address(addr)
            for sym, addr in (registry_entry.assets or {}).items()
        }

    def _get_erc20_contract(self, address: str) -> Contract:
        return self.w3.eth.contract(address=Web3.to_checksum_address(address), abi=_ERC20_ABI)

    async def _retry_call(self, func, max_retries: int = 3) -> Any:  # type: ignore[type-arg]
        """Call a sync function in a thread with exponential backoff retries."""
        backoff = (1, 2, 4)
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                return await asyncio.to_thread(func)
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    wait = backoff[attempt]
                    logger.warning(
                        "RPC call attempt %d/%d failed, retrying in %ds: %s",
                        attempt + 1,
                        max_retries,
                        wait,
                        exc,
                    )
                    await asyncio.sleep(wait)
        logger.error("RPC call exhausted all %d retries: %s", max_retries, last_exc)
        raise last_exc  # type: ignore[misc]

    async def fetch_reserves(self) -> list[dict[str, object]]:
        """Fetch reserve data for all tracked assets. Implements LendingProvider protocol."""
        all_reserves: list[str] = await self._retry_call(
            lambda: self.pool.functions.getReservesList().call()
        )
        all_reserves_lower = {r.lower() for r in all_reserves}

        # Filter to tracked assets that actually exist in the pool
        tracked = {
            sym: addr for sym, addr in self.assets.items() if addr.lower() in all_reserves_lower
        }

        if not tracked:
            logger.warning("No tracked Aave reserves found in pool")
            return []

        results: list[dict[str, object]] = []
        for symbol, address in tracked.items():
            try:
                data = await self._fetch_one_reserve(address, symbol)
                results.append(data)
            except Exception:
                logger.exception(
                    "Failed to fetch reserve data for %s (%s), skipping", symbol, address
                )
        return results

    async def _fetch_one_reserve(self, address: str, symbol: str) -> dict[str, object]:
        """Fetch and compute all metrics for a single reserve asset."""
        raw_tuple = await self._retry_call(
            lambda: self.pool.functions.getReserveData(address).call()
        )

        # configuration is decoded as a plain uint256 now (ABI fixed). The first
        # element of raw_tuple is the config bitmask directly.
        rd = _ReserveData(
            configuration_data=int(raw_tuple[0]),
            liquidity_index=raw_tuple[1],
            liquidity_rate=raw_tuple[2],
            variable_borrow_index=raw_tuple[3],
            variable_borrow_rate=raw_tuple[4],
            stable_borrow_rate=raw_tuple[5],
            last_update_timestamp=raw_tuple[6],
            reserve_id=raw_tuple[7],
            a_token_address=raw_tuple[8],
            stable_debt_token_address=raw_tuple[9],
            variable_debt_token_address=raw_tuple[10],
            interest_rate_strategy_address=raw_tuple[11],
        )

        # Fetch token supplies
        # ponytail: sequential; add parallel fetching if latency matters
        a_token_contract = self._get_erc20_contract(rd.a_token_address)
        var_debt_contract = self._get_erc20_contract(rd.variable_debt_token_address)

        total_supplied_raw: int = await self._retry_call(
            lambda: a_token_contract.functions.totalSupply().call()
        )
        total_borrowed_raw: int = await self._retry_call(
            lambda: var_debt_contract.functions.totalSupply().call()
        )

        total_supplied = float(total_supplied_raw)
        total_borrowed = float(total_borrowed_raw)

        utilization = total_borrowed / total_supplied if total_supplied > 0 else 0.0

        deposit_apy = _ray_to_apy_pct(rd.liquidity_rate)
        borrow_apy = _ray_to_apy_pct(rd.variable_borrow_rate)

        config = _parse_config_data(rd.configuration_data)

        # Build raw payload for JSONB storage
        raw_payload: dict[str, object] = {
            "configuration": {
                "data": hex(rd.configuration_data),
                "ltv_pct": config["ltv_pct"],
                "liquidation_threshold_pct": config["liquidation_threshold_pct"],
                "reserve_factor_pct": config["reserve_factor_pct"],
            },
            "liquidity_index": str(rd.liquidity_index),
            "liquidity_rate_ray": str(rd.liquidity_rate),
            "variable_borrow_index": str(rd.variable_borrow_index),
            "variable_borrow_rate_ray": str(rd.variable_borrow_rate),
            "stable_borrow_rate_ray": str(rd.stable_borrow_rate),
            "last_update_timestamp": rd.last_update_timestamp,
            "a_token_address": rd.a_token_address,
            "variable_debt_token_address": rd.variable_debt_token_address,
            "total_supplied_raw": str(total_supplied_raw),
            "total_borrowed_raw": str(total_borrowed_raw),
        }

        return {
            "chain": self.chain,
            "protocol": self.protocol,
            "market_type": "lending",
            "reward_apy": None,
            "asset": symbol,
            "deposit_apy": deposit_apy,
            "borrow_apy": borrow_apy,
            "utilization": utilization,
            "available_liquidity": total_supplied - total_borrowed,
            "total_supplied": total_supplied,
            "total_borrowed": total_borrowed,
            "tvl": total_supplied,
            "ltv_pct": config["ltv_pct"],
            "liquidation_threshold_pct": config["liquidation_threshold_pct"],
            "reserve_factor_pct": config["reserve_factor_pct"],
            "raw_payload": raw_payload,
        }
