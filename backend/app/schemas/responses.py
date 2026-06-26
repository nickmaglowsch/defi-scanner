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
    funding_rate: float | None = None
    annualized_funding: float | None = None
    open_interest: float | None = None
    volume_24h: float | None = None
    long_short_ratio: float | None = None
    mark_price: float | None = None
    index_price: float | None = None


class LoopOpportunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    protocol: str
    asset: str
    deposit_apy: float | None = None
    borrow_apy: float | None = None
    effective_yield: float | None = None
    leverage: float | None = None
    safety_margin: float | None = None
    liquidation_distance: float | None = None
    risk_score: float | None = None
    score: float
    rank: int


class CarryOpportunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    protocol: str
    asset: str
    funding_yield: float | None = None
    spot_yield: float | None = None
    borrow_cost: float | None = None
    trading_fees: float | None = None
    net_carry: float | None = None
    risk_score: float | None = None
    score: float
    rank: int


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
