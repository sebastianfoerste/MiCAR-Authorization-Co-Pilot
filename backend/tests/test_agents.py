from __future__ import annotations

from micar.agents.runtime import AGENT_DEFINITIONS, draft_quality_findings_for_clause


def test_agent_catalog_covers_supervised_legal_workflow() -> None:
    assert set(AGENT_DEFINITIONS) == {
        "readiness",
        "citation_auditor",
        "draft_qa",
        "source_monitor",
        "package_review",
        "template_improvement",
    }


def test_draft_qa_detects_review_markers_without_mutating_output() -> None:
    findings = draft_quality_findings_for_clause(
        clause_key="governance",
        title="Governance-Konzept",
        rendered_prose="## Governance\n\n[Lawyer-Review: Nachweise prüfen.]",
        citations=[{"citation": "Art. 68 VO (EU) 2023/1114 (MiCAR)", "anchor_id": 1}],
    )

    assert findings == [
        {
            "severity": "medium",
            "title": "Governance-Konzept: Review-Marker offen",
            "body": (
                "Der Entwurf enthält ausdrückliche Review-Marker. "
                "Diese sind sinnvoll, aber vor Export bewusst abzuarbeiten."
            ),
            "evidence": {"clause_key": "governance", "marker": "lawyer_review"},
        },
        {
            "severity": "low",
            "title": "Governance-Konzept: sehr kurzer Entwurf",
            "body": "Der Entwurf ist ungewöhnlich kurz und sollte inhaltlich geprüft werden.",
            "evidence": {"clause_key": "governance", "character_count": 49},
        },
    ]


def test_draft_qa_blocks_empty_uncited_clause() -> None:
    findings = draft_quality_findings_for_clause(
        clause_key="authorization_application",
        title="Antrag",
        rendered_prose="",
        citations=[],
    )

    assert [finding["severity"] for finding in findings] == ["high", "high"]
    assert {finding["title"] for finding in findings} == {
        "Antrag: kein Entwurfstext",
        "Antrag: keine Zitate",
    }
