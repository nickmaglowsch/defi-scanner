from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CarryCalculation(Base):
    __tablename__ = "carry_calculations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    funding_snapshot_id: Mapped[str] = mapped_column(String(36), nullable=False)
    lending_snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    calc_version: Mapped[str] = mapped_column(String, default="carry-v1", server_default="carry-v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    spot_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    funding_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    borrow_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    trading_fees: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_carry: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_annual_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    penalty_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
