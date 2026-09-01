"""team invitations; collapse the owner role into admin

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-01 00:00:00.000000+00:00

Roles are now admin / member (viewer reserved). The single immutable ``owner`` is
replaced by last-admin protection in the service layer (ADR-0026). Existing
``OWNER`` memberships become ``ADMIN`` — additive and reversible in spirit (the
downgrade cannot restore which admin was formerly the owner, by design).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_invitations_token_hash"),
    )
    op.create_index(
        "uq_invitations_org_email_pending",
        "invitations",
        ["organization_id", "email"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.create_index("ix_invitations_org_status", "invitations", ["organization_id", "status"])

    # Collapse owner → admin.
    op.execute("UPDATE memberships SET role = 'ADMIN' WHERE role = 'OWNER'")


def downgrade() -> None:
    op.drop_index("ix_invitations_org_status", table_name="invitations")
    op.drop_index("uq_invitations_org_email_pending", table_name="invitations")
    op.drop_table("invitations")
