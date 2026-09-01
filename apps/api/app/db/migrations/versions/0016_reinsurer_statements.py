"""reinsurer statements + reconciliation lines

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-01 00:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reinsurer_statements",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("statement_date", sa.Date(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "reinsurer_statement_lines",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("statement_id", sa.Uuid(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("reinsurer_name", sa.String(length=300), nullable=False),
        sa.Column("reference", sa.String(length=300), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("their_agreed", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("their_paid", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("matched_recoverable_id", sa.Uuid(), nullable=True),
        sa.Column("findings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resolved", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["statement_id"], ["reinsurer_statements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["matched_recoverable_id"], ["recoverables.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("statement_id", "row_number", name="uq_reinsurer_statement_lines_row"),
    )


def downgrade() -> None:
    op.drop_table("reinsurer_statement_lines")
    op.drop_table("reinsurer_statements")
