from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LoopCalculation(Base):
    __tablename__ = "loop_calculations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    lending_snapshot_id: Mapped[str] = mapped_column(String(36), nullable=False)
    calc_version: Mapped[str] = mapped_column(String, default="loop-v1", server_default="loop-v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    input_capital: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_target_ltv: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_safety_buffer: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_max_loops: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deposited_capital: Mapped[float | None] = mapped_column(Float, nullable=True)
    borrowed_capital: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_apy: Mapped[float | None] = mapped_column(Float, nullable=True)
    effective_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    leverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    safety_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    liquidation_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
