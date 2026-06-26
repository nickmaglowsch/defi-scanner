from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    alert_type: Mapped[str] = mapped_column(String, nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    triggered_value: Mapped[float] = mapped_column(Float, nullable=False)
    market_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("markets.id"), nullable=True
    )
    snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="fired", server_default="fired")
    fired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    raw_message: Mapped[str | None] = mapped_column(Text, nullable=True)
