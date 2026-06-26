"""initial

Revision ID: 250141bdc9f8
Revises:
Create Date: 2026-06-25 23:11:38.568387

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "250141bdc9f8"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── protocols ──────────────────────────────────────────────────────
    op.create_table(
        "protocols",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(), unique=True, nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("chain", sa.String(), nullable=True),
        sa.Column("risk_score", sa.Float(), default=0, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── markets ────────────────────────────────────────────────────────
    op.create_table(
        "markets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "protocol_id",
            sa.String(36),
            sa.ForeignKey("protocols.id"),
            nullable=False,
        ),
        sa.Column("asset", sa.String(), nullable=False),
        sa.Column("market_type", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── lending_snapshots ──────────────────────────────────────────────
    # Composite PK (id, observed_at) required by TimescaleDB for hypertable.
    # FK references from calculation tables are soft (UUIDs unique at app level).
    op.create_table(
        "lending_snapshots",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column(
            "market_id",
            sa.String(36),
            sa.ForeignKey("markets.id"),
            nullable=False,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deposit_apy", sa.Float(), nullable=True),
        sa.Column("borrow_apy", sa.Float(), nullable=True),
        sa.Column("utilization", sa.Float(), nullable=True),
        sa.Column("available_liquidity", sa.Float(), nullable=True),
        sa.Column("total_supplied", sa.Float(), nullable=True),
        sa.Column("total_borrowed", sa.Float(), nullable=True),
        sa.Column("tvl", sa.Float(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id", "observed_at"),
        sa.UniqueConstraint(
            "market_id",
            "observed_at",
            name="uq_lending_snapshots_market_observed",
        ),
    )
    op.create_index(
        "ix_lending_snapshots_observed_at",
        "lending_snapshots",
        ["observed_at"],
    )
    op.create_index(
        "ix_lending_snapshots_market_observed",
        "lending_snapshots",
        ["market_id", "observed_at"],
    )

    # ── funding_snapshots ──────────────────────────────────────────────
    # Composite PK (id, observed_at) required by TimescaleDB for hypertable.
    # FK references from calculation tables are soft (UUIDs unique at app level).
    op.create_table(
        "funding_snapshots",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column(
            "market_id",
            sa.String(36),
            sa.ForeignKey("markets.id"),
            nullable=False,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("funding_rate", sa.Float(), nullable=True),
        sa.Column("funding_interval_hours", sa.Float(), nullable=True),
        sa.Column("annualized_funding", sa.Float(), nullable=True),
        sa.Column("open_interest", sa.Float(), nullable=True),
        sa.Column("volume_24h", sa.Float(), nullable=True),
        sa.Column("long_short_ratio", sa.Float(), nullable=True),
        sa.Column("mark_price", sa.Float(), nullable=True),
        sa.Column("index_price", sa.Float(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id", "observed_at"),
        sa.UniqueConstraint(
            "market_id",
            "observed_at",
            name="uq_funding_snapshots_market_observed",
        ),
    )
    op.create_index(
        "ix_funding_snapshots_observed_at",
        "funding_snapshots",
        ["observed_at"],
    )
    op.create_index(
        "ix_funding_snapshots_market_observed",
        "funding_snapshots",
        ["market_id", "observed_at"],
    )

    # ── loop_calculations ──────────────────────────────────────────────
    op.create_table(
        "loop_calculations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "lending_snapshot_id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "calc_version",
            sa.String(),
            default="loop-v1",
            server_default="loop-v1",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("input_capital", sa.Float(), nullable=True),
        sa.Column("input_target_ltv", sa.Float(), nullable=True),
        sa.Column("input_safety_buffer", sa.Float(), nullable=True),
        sa.Column("input_max_loops", sa.Integer(), nullable=True),
        sa.Column("deposited_capital", sa.Float(), nullable=True),
        sa.Column("borrowed_capital", sa.Float(), nullable=True),
        sa.Column("net_apy", sa.Float(), nullable=True),
        sa.Column("effective_yield", sa.Float(), nullable=True),
        sa.Column("leverage", sa.Float(), nullable=True),
        sa.Column("safety_margin", sa.Float(), nullable=True),
        sa.Column("liquidation_distance", sa.Float(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
    )

    # ── carry_calculations ─────────────────────────────────────────────
    op.create_table(
        "carry_calculations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "funding_snapshot_id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "lending_snapshot_id",
            sa.String(36),
            nullable=True,
        ),
        sa.Column(
            "calc_version",
            sa.String(),
            default="carry-v1",
            server_default="carry-v1",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("spot_yield", sa.Float(), nullable=True),
        sa.Column("funding_yield", sa.Float(), nullable=True),
        sa.Column("borrow_cost", sa.Float(), nullable=True),
        sa.Column("trading_fees", sa.Float(), nullable=True),
        sa.Column("net_carry", sa.Float(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("expected_annual_return", sa.Float(), nullable=True),
    )

    # ── alerts ─────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("alert_type", sa.String(), nullable=False),
        sa.Column("threshold_value", sa.Float(), nullable=False),
        sa.Column("triggered_value", sa.Float(), nullable=False),
        sa.Column(
            "market_id",
            sa.String(36),
            sa.ForeignKey("markets.id"),
            nullable=True,
        ),
        sa.Column("snapshot_id", sa.String(36), nullable=True),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.String(),
            default="fired",
            server_default="fired",
        ),
        sa.Column(
            "fired_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("raw_message", sa.Text(), nullable=True),
    )

    # ── TimescaleDB extension + hypertables ────────────────────────────
    # Guarded: works on both TimescaleDB and plain PostgreSQL.
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN "
        "PERFORM create_hypertable('lending_snapshots', 'observed_at', if_not_exists => TRUE); "
        "PERFORM create_hypertable('funding_snapshots', 'observed_at', if_not_exists => TRUE); "
        "END IF; END $$"
    )


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("carry_calculations")
    op.drop_table("loop_calculations")
    op.drop_table("funding_snapshots")
    op.drop_table("lending_snapshots")
    op.drop_table("markets")
    op.drop_table("protocols")
