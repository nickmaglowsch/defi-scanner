"""protocol metadata: real confidence signals (address, deployed_at, audits).

Revision ID: 7f2c1a4b9d30
Revises: 250141bdc9f8
Create Date: 2026-06-26 01:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7f2c1a4b9d30"
down_revision: str | Sequence[str] | None = "250141bdc9f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("protocols", schema=None) as batch_op:
        batch_op.add_column(sa.Column("address", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column("audit_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("audit_source", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("metadata_updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("protocols", schema=None) as batch_op:
        batch_op.drop_column("metadata_updated_at")
        batch_op.drop_column("audit_source")
        batch_op.drop_column("audit_count")
        batch_op.drop_column("deployed_at")
        batch_op.drop_column("address")