"""anchor review note

Revision ID: 0003_anchor_review_note
Revises: 0002_anchor_provenance
Create Date: 2026-05-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_anchor_review_note"
down_revision: str | None = "0002_anchor_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("anchors", sa.Column("review_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("anchors", "review_note")
