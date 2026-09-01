"""reinstatement premium terms on a treaty layer

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-01 00:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "treaty_layers",
        sa.Column("deposit_premium", sa.Numeric(precision=20, scale=2), nullable=True),
    )
    op.add_column(
        "treaty_layers",
        sa.Column("reinstatement_rates", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "treaty_layers", sa.Column("reinstatement_basis", sa.String(length=16), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("treaty_layers", "reinstatement_basis")
    op.drop_column("treaty_layers", "reinstatement_rates")
    op.drop_column("treaty_layers", "deposit_premium")
