"""Confirm the ORM metadata is well-formed without needing a live Postgres."""

from __future__ import annotations

from micar.models import Base


def test_expected_tables_registered() -> None:
    expected = {
        "users",
        "mandates",
        "intake_sections",
        "anchors",
        "anchor_changes",
        "templates",
        "template_uses",
        "artifacts",
        "audit_events",
        "agent_runs",
        "agent_steps",
        "agent_findings",
        "agent_actions",
    }
    assert set(Base.metadata.tables.keys()) == expected


def test_unique_constraints() -> None:
    tables = Base.metadata.tables
    assert any(c.name == "uq_users_email" for c in tables["users"].constraints) or any(
        col.unique for col in tables["users"].columns if col.name == "email"
    )
    assert any(c.name == "uq_anchor_citation_version" for c in tables["anchors"].constraints)
    assert any(c.name == "uq_template_track_clause_ver" for c in tables["templates"].constraints)
    assert any(c.name == "uq_intake_section_mandate_key" for c in tables["intake_sections"].constraints)


def test_anchor_review_note_column_registered() -> None:
    assert "review_note" in Base.metadata.tables["anchors"].columns


def test_agent_tables_register_review_gated_columns() -> None:
    tables = Base.metadata.tables
    assert "input_snapshot" in tables["agent_runs"].columns
    assert "evidence" in tables["agent_findings"].columns
    assert "payload" in tables["agent_actions"].columns
    assert "decided_at" in tables["agent_actions"].columns
