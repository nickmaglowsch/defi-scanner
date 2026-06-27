from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CrossProtocolCalculation(Base):
    __tablename__ = "cross_protocol_calculations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    deposit_market_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("markets.id"), nullable=False
    )
    borrow_market_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("markets.id"), nullable=False
    )
    calc_version: Mapped[str] = mapped_column(
        String, default="cross-protocol-v1", server_default="cross-protocol-v1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deposit_apy: Mapped[float | None] = mapped_column(Float, nullable=True)
    borrow_apy: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_spread: Mapped[float | None] = mapped_column(Float, nullable=True)
    leverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    penalty_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
