"""initial schema — full Phase 0..6 tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-20
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="lawyer"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "mandates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("client_label", sa.String(length=255), nullable=True),
        sa.Column("track", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("target_filing_date", sa.Date(), nullable=True),
        sa.Column("redact_client_identifiers", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_mandates_track", "mandates", ["track"])
    op.create_index("ix_mandates_state", "mandates", ["state"])
    op.create_index("ix_mandates_owner_id", "mandates", ["owner_id"])

    op.create_table(
        "intake_sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mandate_id", sa.Integer(), sa.ForeignKey("mandates.id"), nullable=False),
        sa.Column("section_key", sa.String(length=64), nullable=False),
        sa.Column("answers", postgresql.JSONB(), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("mandate_id", "section_key", name="uq_intake_section_mandate_key"),
    )
    op.create_index("ix_intake_sections_mandate_id", "intake_sections", ["mandate_id"])

    op.create_table(
        "anchors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("authority", sa.String(length=32), nullable=False),
        sa.Column("citation_canonical", sa.String(length=512), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("binding_force_note", sa.Text(), nullable=True),
        sa.Column("source_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("citation_canonical", "version", name="uq_anchor_citation_version"),
    )
    op.create_index("ix_anchors_level", "anchors", ["level"])
    op.create_index("ix_anchors_authority", "anchors", ["authority"])
    op.create_index("ix_anchors_citation_canonical", "anchors", ["citation_canonical"])
    op.create_index("ix_anchors_effective", "anchors", ["effective_from", "effective_to"])

    op.create_table(
        "anchor_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("anchor_id_prev", sa.Integer(), sa.ForeignKey("anchors.id"), nullable=True),
        sa.Column("anchor_id_new", sa.Integer(), sa.ForeignKey("anchors.id"), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("triage_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_anchor_changes_status_detected",
        "anchor_changes",
        ["triage_status", "detected_at"],
    )

    op.create_table(
        "templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("track", sa.String(length=16), nullable=False),
        sa.Column("clause_key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("anchor_refs", postgresql.JSONB(), nullable=True),
        sa.Column("facts_schema", postgresql.JSONB(), nullable=True),
        sa.Column("prose_skeleton", sa.Text(), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("last_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("track", "clause_key", "version", name="uq_template_track_clause_ver"),
    )
    op.create_index("ix_templates_track", "templates", ["track"])
    op.create_index("ix_templates_clause_key", "templates", ["clause_key"])

    op.create_table(
        "template_uses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mandate_id", sa.Integer(), sa.ForeignKey("mandates.id"), nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("templates.id"), nullable=False),
        sa.Column("template_version", sa.String(length=64), nullable=False),
        sa.Column("facts_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("rendered_prose", sa.Text(), nullable=True),
        sa.Column("citations", postgresql.JSONB(), nullable=True),
        sa.Column("llm_run_id", sa.String(length=128), nullable=True),
        sa.Column("lawyer_review_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("flagged_by_change_id", sa.Integer(), sa.ForeignKey("anchor_changes.id"), nullable=True),
        sa.Column("rendered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_template_uses_mandate_id", "template_uses", ["mandate_id"])
    op.create_index("ix_template_uses_template_id", "template_uses", ["template_id"])
    op.create_index("ix_template_uses_flagged", "template_uses", ["flagged_by_change_id"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mandate_id", sa.Integer(), sa.ForeignKey("mandates.id"), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("template_use_ids", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_artifacts_mandate_id", "artifacts", ["mandate_id"])
    op.create_index("ix_artifacts_kind", "artifacts", ["kind"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("mandate_id", sa.Integer(), sa.ForeignKey("mandates.id"), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("payload_redacted", postgresql.JSONB(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])
    op.create_index("ix_audit_events_mandate_id", "audit_events", ["mandate_id"])
    op.create_index("ix_audit_events_kind", "audit_events", ["kind"])
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("artifacts")
    op.drop_table("template_uses")
    op.drop_table("templates")
    op.drop_table("anchor_changes")
    op.drop_table("anchors")
    op.drop_table("intake_sections")
    op.drop_table("mandates")
    op.drop_table("users")
