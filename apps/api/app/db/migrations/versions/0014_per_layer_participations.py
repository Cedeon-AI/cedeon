"""per-layer participations

A participation row may now belong to a single treaty layer (``treaty_layer_id``)
instead of the whole programme. NULL is the programme-wide panel, unchanged.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-01 00:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("treaty_participations", sa.Column("treaty_layer_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_treaty_participations_treaty_layer_id_treaty_layers",
        "treaty_participations",
        "treaty_layers",
        ["treaty_layer_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # Replace the version-wide unique constraint with two partial unique indexes:
    # one for the programme panel (layer id NULL), one per layer.
    op.drop_constraint(
        "uq_treaty_participations_version_reinsurer", "treaty_participations", type_="unique"
    )
    op.create_index(
        "uq_treaty_participations_version_reinsurer",
        "treaty_participations",
        ["treaty_version_id", "reinsurer_id"],
        unique=True,
        postgresql_where=sa.text("treaty_layer_id IS NULL"),
    )
    op.create_index(
        "uq_treaty_participations_layer_reinsurer",
        "treaty_participations",
        ["treaty_version_id", "treaty_layer_id", "reinsurer_id"],
        unique=True,
        postgresql_where=sa.text("treaty_layer_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_treaty_participations_layer_reinsurer", "treaty_participations")
    op.drop_index("uq_treaty_participations_version_reinsurer", "treaty_participations")
    op.create_unique_constraint(
        "uq_treaty_participations_version_reinsurer",
        "treaty_participations",
        ["treaty_version_id", "reinsurer_id"],
    )
    op.drop_constraint(
        "fk_treaty_participations_treaty_layer_id_treaty_layers",
        "treaty_participations",
        type_="foreignkey",
    )
    op.drop_column("treaty_participations", "treaty_layer_id")
