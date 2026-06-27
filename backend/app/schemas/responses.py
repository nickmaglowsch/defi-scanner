"""Pydantic v2 response schemas — no ORM leakage."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProtocolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: str
    chain: str | None = None
    risk_score: float = 0.0


class MarketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    protocol_id: str
    asset: str
    market_type: str


class LendingSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    market_id: str
    observed_at: datetime
    deposit_apy: float | None = None
    borrow_apy: float | None = None
    utilization: float | None = None
    available_liquidity: float | None = None
    total_supplied: float | None = None
    total_borrowed: float | None = None
    tvl: float | None = None


class FundingSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    market_id: str
    observed_at: datetime
    asset: str
    protocol: str
    funding_rate: float | None = None
    funding_interval_hours: float | None = None
    annualized_funding: float | None = None
    open_interest: float | None = None
    volume_24h: float | None = None
    long_short_ratio: float | None = None
    mark_price: float | None = None
    index_price: float | None = None


class YieldHistoryOut(BaseModel):
    today: float | None = None
    yesterday: float | None = None
    avg_7d: float | None = None
    avg_30d: float | None = None


class OpportunityOut(BaseModel):
    """Generic opportunity schema with strategy_type discriminator.

    strategy_details holds strategy-specific fields (loop leverage,
    carry funding yield, etc.) so this schema stays stable as new
    strategy types are added.
    """

    model_config = ConfigDict(from_attributes=True)

    # Common identity fields
    strategy_type: str  # "loop" | "carry" | future types
    protocol: str
    asset: str
    chain: str | None = None

    # Common financial fields
    net_apy: float | None = None  # effective_yield for loop, net_carry for carry
    risk_score: float | None = None
    score: float
    rank: int

    # Task-04 enrichment
    market_id: str | None = None
    breakdown: dict[str, float] | None = None
    weights: dict[str, float] | None = None
    rating: float | None = None
    rating_label: str | None = None
    confidence: float | None = None
    medal: str | None = None
    sharpe: float | None = None
    history: YieldHistoryOut | None = None

    # Strategy-specific details (loop leverage, carry funding yield, etc.)
    strategy_details: dict = {}

    # Task-10 future fields (anomaly context)
    percentile_90d: float | None = None
    historical_rank: str | None = None


# ponytail: deprecated aliases — keep for any external code still importing them;
# all internal code now constructs OpportunityOut directly.
class LoopOpportunityOut(OpportunityOut):
    """Deprecated alias for OpportunityOut with strategy_type='loop'."""

    deposit_apy: float | None = None
    borrow_apy: float | None = None
    effective_yield: float | None = None
    leverage: float | None = None
    safety_margin: float | None = None
    liquidation_distance: float | None = None


class CarryOpportunityOut(OpportunityOut):
    """Deprecated alias for OpportunityOut with strategy_type='carry'."""

    funding_yield: float | None = None
    spot_yield: float | None = None
    borrow_cost: float | None = None
    trading_fees: float | None = None
    net_carry: float | None = None


class HistoryPointOut(BaseModel):
    observed_at: datetime
    value: float


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_type: str
    threshold_value: float
    triggered_value: float
    market_id: str | None = None
    channel: str
    status: str
    fired_at: datetime
