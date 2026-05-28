"""Add supervised agent run tables.

Revision ID: 0004_agent_runs
Revises: 0003_anchor_review_note
Create Date: 2026-05-28 22:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_agent_runs"
down_revision: str | None = "0003_anchor_review_note"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mandate_id", sa.Integer(), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("agent_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["mandate_id"], ["mandates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_runs_actor_id"), "agent_runs", ["actor_id"], unique=False)
    op.create_index(op.f("ix_agent_runs_agent_key"), "agent_runs", ["agent_key"], unique=False)
    op.create_index(op.f("ix_agent_runs_created_at"), "agent_runs", ["created_at"], unique=False)
    op.create_index(op.f("ix_agent_runs_mandate_id"), "agent_runs", ["mandate_id"], unique=False)
    op.create_index(op.f("ix_agent_runs_status"), "agent_runs", ["status"], unique=False)
    op.create_index("ix_agent_runs_mandate_created", "agent_runs", ["mandate_id", "created_at"], unique=False)

    op.create_table(
        "agent_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step_key", sa.String(length=96), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_steps_run_id"), "agent_steps", ["run_id"], unique=False)

    op.create_table(
        "agent_findings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("mandate_id", sa.Integer(), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["mandate_id"], ["mandates.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_findings_mandate_id"), "agent_findings", ["mandate_id"], unique=False)
    op.create_index(op.f("ix_agent_findings_run_id"), "agent_findings", ["run_id"], unique=False)
    op.create_index(op.f("ix_agent_findings_severity"), "agent_findings", ["severity"], unique=False)
    op.create_index(op.f("ix_agent_findings_status"), "agent_findings", ["status"], unique=False)
    op.create_index(
        "ix_agent_findings_mandate_status", "agent_findings", ["mandate_id", "status"], unique=False
    )

    op.create_table(
        "agent_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("mandate_id", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["mandate_id"], ["mandates.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_actions_action_type"), "agent_actions", ["action_type"], unique=False)
    op.create_index(op.f("ix_agent_actions_mandate_id"), "agent_actions", ["mandate_id"], unique=False)
    op.create_index(op.f("ix_agent_actions_run_id"), "agent_actions", ["run_id"], unique=False)
    op.create_index(op.f("ix_agent_actions_status"), "agent_actions", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_actions_status"), table_name="agent_actions")
    op.drop_index(op.f("ix_agent_actions_run_id"), table_name="agent_actions")
    op.drop_index(op.f("ix_agent_actions_mandate_id"), table_name="agent_actions")
    op.drop_index(op.f("ix_agent_actions_action_type"), table_name="agent_actions")
    op.drop_table("agent_actions")

    op.drop_index("ix_agent_findings_mandate_status", table_name="agent_findings")
    op.drop_index(op.f("ix_agent_findings_status"), table_name="agent_findings")
    op.drop_index(op.f("ix_agent_findings_severity"), table_name="agent_findings")
    op.drop_index(op.f("ix_agent_findings_run_id"), table_name="agent_findings")
    op.drop_index(op.f("ix_agent_findings_mandate_id"), table_name="agent_findings")
    op.drop_table("agent_findings")

    op.drop_index(op.f("ix_agent_steps_run_id"), table_name="agent_steps")
    op.drop_table("agent_steps")

    op.drop_index("ix_agent_runs_mandate_created", table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_status"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_mandate_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_created_at"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_agent_key"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_actor_id"), table_name="agent_runs")
    op.drop_table("agent_runs")
