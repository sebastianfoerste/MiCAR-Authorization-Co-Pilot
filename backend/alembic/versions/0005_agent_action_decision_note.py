"""Add review notes to agent action decisions.

Revision ID: 0005_agent_action_decision_note
Revises: 0004_agent_runs
Create Date: 2026-05-29 08:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_agent_action_decision_note"
down_revision: str | None = "0004_agent_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_actions", sa.Column("decision_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_actions", "decision_note")
