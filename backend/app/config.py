from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, overridable via DEFI_* env vars."""

    model_config = SettingsConfigDict(env_prefix="DEFI_")

    DATABASE_URL: str = "postgresql+asyncpg://defi:defi@localhost:5432/defi_scanner"
    RPC_URL: str = "https://eth.llamarpc.com"
    HYPERLIQUID_API_URL: str = "https://api.hyperliquid.xyz"
    # ── Protocol metadata collectors (real confidence signals) ───────────────
    # DefiLlama's public /protocols list (no API key) supplies per-protocol
    # `address`, `chain`, and audit presence. Override to point at a mirror or
    # a local registry file served over HTTP for offline/test environments.
    DEFI_LLAMA_PROTOCOLS_URL: str = "https://api.llama.fi/protocols"
    # How often the metadata collectors refresh. Deploy/audit info changes
    # rarely, so hourly is plenty and keeps free-RPC rate limits happy.
    DEFI_PROTOCOL_METADATA_INTERVAL_SECONDS: int = 3600
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    COLLECTOR_INTERVAL_SECONDS: int = 300
    AAVE_POOL_ADDRESS: str = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
    AAVE_ASSETS: str = (
        "USDC:0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48,"
        "USDT:0xdAC17F958D2ee523a2206206994597C13D831ec7,"
        "DAI:0x6B175474E89094C44Da98b954EedeAC495271d0F,"
        "WETH:0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2,"
        "wstETH:0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0"
    )
    RANKER_WEIGHTS: str = (
        '{"yield_score": 1.0, "liquidity_score": 1.0, "tvl_score": 1.0, '
        '"stability_score": 1.0, "utilization_penalty": 1.0, '
        '"volatility_penalty": 1.0, "protocol_risk": 1.0}'
    )
    DEFI_VOLATILITY_WINDOW: int = 20
    ALERT_LOOP_YIELD_THRESHOLD: float = 10.0
    # Loop opps with a nominal spread (deposit_apy − borrow_apy) below this floor
    # are filtered out before scoring. 0.0 = require non-inverted rates (leverage
    # can't manufacture yield from a negative pre-leverage edge); raise to demand
    # a thicker pre-leverage margin for rate drift, gas, and fees.
    DEFI_LOOP_MIN_NOMINAL_SPREAD: float = 0.0
    ALERT_FUNDING_RATE_THRESHOLD: float = 20.0
    ALERT_NET_CARRY_THRESHOLD: float = 12.0
    ALERT_BORROW_APY_THRESHOLD: float = 3.0
    ALERT_COOLDOWN_MINUTES: int = 60
    ALERT_INTERVAL_SECONDS: int = 300


settings = Settings()
