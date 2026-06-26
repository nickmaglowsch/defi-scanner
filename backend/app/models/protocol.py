from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Protocol(Base):
    __tablename__ = "protocols"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    chain: Mapped[str | None] = mapped_column(String, nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # ── Real metadata signals collected by app.collectors.protocol_metadata ──
    # `address`: main on-chain contract address (from DefiLlama). Used by
    #   ProtocolAgeCollector to resolve `deployed_at` via get_code binary search.
    address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # `deployed_at`: timestamp of the block where `address` was deployed. None
    #   until resolved (or unknown for non-EVM protocols like Hyperliquid).
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # `audit_count`: number of known audits (0 = no audits known). Sourced from
    #   DefiLlama presence today; a real audit-count collector can enrich later.
    audit_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    audit_source: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
