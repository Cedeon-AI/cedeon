"""signup access codes; per-organization monthly AI budget

Gate on org creation (``signup_mode``) plus a spend cap so a demo can be opened to
customers without self-serve credit burn (ADR-0028). Additive and reversible.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signup_codes",
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("max_uses", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("redeemed_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("grant_ai_budget_usd", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash", name="uq_signup_codes_code_hash"),
    )

    op.add_column(
        "organizations",
        sa.Column("ai_budget_usd", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("ai_budget_notified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "ai_budget_notified_at")
    op.drop_column("organizations", "ai_budget_usd")
    op.drop_table("signup_codes")
