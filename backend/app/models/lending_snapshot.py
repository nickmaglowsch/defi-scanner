from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LendingSnapshot(Base):
    __tablename__ = "lending_snapshots"
    __table_args__ = (
        PrimaryKeyConstraint("id", "observed_at"),
        UniqueConstraint("market_id", "observed_at", name="uq_lending_snapshots_market_observed"),
    )

    id: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()))
    market_id: Mapped[str] = mapped_column(String(36), ForeignKey("markets.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    deposit_apy: Mapped[float | None] = mapped_column(Float, nullable=True)
    borrow_apy: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward_apy: Mapped[float | None] = mapped_column(Float, nullable=True)
    utilization: Mapped[float | None] = mapped_column(Float, nullable=True)
    available_liquidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_supplied: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_borrowed: Mapped[float | None] = mapped_column(Float, nullable=True)
    tvl: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
