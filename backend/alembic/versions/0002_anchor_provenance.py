"""anchor source provenance and review gate

Revision ID: 0002_anchor_provenance
Revises: 0001_initial
Create Date: 2026-05-26
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_anchor_provenance"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "anchors",
        sa.Column("source_status", sa.String(length=32), nullable=False, server_default="seed_unverified"),
    )
    op.add_column("anchors", sa.Column("source_retrieved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("anchors", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("anchors", sa.Column("reviewed_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_anchors_reviewed_by_users",
        "anchors",
        "users",
        ["reviewed_by"],
        ["id"],
    )
    op.create_index("ix_anchors_source_status", "anchors", ["source_status"])


def downgrade() -> None:
    op.drop_index("ix_anchors_source_status", table_name="anchors")
    op.drop_constraint("fk_anchors_reviewed_by_users", "anchors", type_="foreignkey")
    op.drop_column("anchors", "reviewed_by")
    op.drop_column("anchors", "reviewed_at")
    op.drop_column("anchors", "source_retrieved_at")
    op.drop_column("anchors", "source_status")
