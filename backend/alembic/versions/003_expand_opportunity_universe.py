"""expand opportunity universe

Revision ID: a1b2c3d4e5f6
Revises: 7f2c1a4b9d30
Create Date: 2026-06-26 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "7f2c1a4b9d30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── markets ────────────────────────────────────────────────────────
    op.add_column("markets", sa.Column("chain", sa.String(), nullable=True))

    # ── lending_snapshots ──────────────────────────────────────────────
    op.add_column(
        "lending_snapshots", sa.Column("reward_apy", sa.Float(), nullable=True)
    )

    # ── cross_protocol_calculations ────────────────────────────────────
    op.create_table(
        "cross_protocol_calculations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "deposit_market_id",
            sa.String(36),
            sa.ForeignKey("markets.id"),
            nullable=False,
        ),
        sa.Column(
            "borrow_market_id",
            sa.String(36),
            sa.ForeignKey("markets.id"),
            nullable=False,
        ),
        sa.Column(
            "calc_version",
            sa.String(),
            default="cross-protocol-v1",
            server_default="cross-protocol-v1",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deposit_apy", sa.Float(), nullable=True),
        sa.Column("borrow_apy", sa.Float(), nullable=True),
        sa.Column("net_spread", sa.Float(), nullable=True),
        sa.Column("leverage", sa.Float(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("penalty_breakdown", postgresql.JSONB(), nullable=True),
    )

    # ── penalty_breakdown on existing calculation tables ───────────────
    op.add_column(
        "loop_calculations",
        sa.Column("penalty_breakdown", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "carry_calculations",
        sa.Column("penalty_breakdown", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("carry_calculations", "penalty_breakdown")
    op.drop_column("loop_calculations", "penalty_breakdown")
    op.drop_table("cross_protocol_calculations")
    op.drop_column("lending_snapshots", "reward_apy")
    op.drop_column("markets", "chain")
