"""Supervised deterministic agents.

The first agent layer is intentionally local and review-gated. Agents create
findings and proposed actions. They do not mutate legal output, approve
sources, send communications, or create filing packages.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from micar.api.mandates import (
    _draft_blockers,
    _readiness_report,
    _review_blockers,
    _source_blockers,
)
from micar.artifacts.package import latest_template_uses_by_clause, validated_latest_template_uses
from micar.intake.validation import is_mandate_ready_for_generation
from micar.models import (
    AgentAction,
    AgentFinding,
    AgentRun,
    AgentStep,
    Anchor,
    AnchorChange,
    IntakeSection,
    Mandate,
    SourceStatus,
    Template,
    TriageStatus,
)
from micar.templates.registry import load_registry
from micar.tracks.registry import get_track


@dataclass(frozen=True)
class AgentDefinition:
    key: str
    label: str
    description: str


AGENT_DEFINITIONS: dict[str, AgentDefinition] = {
    "readiness": AgentDefinition(
        key="readiness",
        label="Readiness Agent",
        description="Calculates deterministic intake, source, review, and export gates.",
    ),
    "citation_auditor": AgentDefinition(
        key="citation_auditor",
        label="Citation Auditor Agent",
        description="Checks rendered clauses against anchors, source status, and template freshness.",
    ),
    "draft_qa": AgentDefinition(
        key="draft_qa",
        label="Draft QA Agent",
        description="Finds placeholders, review markers, empty drafts, and citation gaps.",
    ),
    "source_monitor": AgentDefinition(
        key="source_monitor",
        label="Source Monitor Agent",
        description="Summarizes source-change and source-verification queues.",
    ),
    "package_review": AgentDefinition(
        key="package_review",
        label="Package Review Agent",
        description="Prepares a final export-readiness memo without creating the package.",
    ),
    "template_improvement": AgentDefinition(
        key="template_improvement",
        label="Template Improvement Agent",
        description="Flags missing templates, weak source coverage, and lawyer-review hotspots.",
    ),
}

MANDATE_AGENT_KEYS = tuple(AGENT_DEFINITIONS.keys())
SUPERVISOR_AGENT_KEY = "supervisor"


def all_agent_catalog() -> list[AgentDefinition]:
    return [AGENT_DEFINITIONS[key] for key in MANDATE_AGENT_KEYS]


def draft_quality_findings_for_clause(
    *,
    clause_key: str,
    title: str,
    rendered_prose: str | None,
    citations: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    prose = rendered_prose or ""
    if not prose.strip():
        findings.append(
            {
                "severity": "high",
                "title": f"{title}: kein Entwurfstext",
                "body": "Die neueste Klausel enthält keinen gespeicherten Entwurfstext.",
                "evidence": {"clause_key": clause_key},
            }
        )
    if "[Lawyer-Review:" in prose or "[Hier füllt" in prose:
        findings.append(
            {
                "severity": "medium",
                "title": f"{title}: Review-Marker offen",
                "body": (
                    "Der Entwurf enthält ausdrückliche Review-Marker. "
                    "Diese sind sinnvoll, aber vor Export bewusst abzuarbeiten."
                ),
                "evidence": {"clause_key": clause_key, "marker": "lawyer_review"},
            }
        )
    if "TODO" in prose or "FIXME" in prose:
        findings.append(
            {
                "severity": "medium",
                "title": f"{title}: technische Platzhalter",
                "body": "Der Entwurf enthält TODO- oder FIXME-Marker.",
                "evidence": {"clause_key": clause_key, "marker": "todo_or_fixme"},
            }
        )
    if prose.strip() and len(prose.strip()) < 200:
        findings.append(
            {
                "severity": "low",
                "title": f"{title}: sehr kurzer Entwurf",
                "body": "Der Entwurf ist ungewöhnlich kurz und sollte inhaltlich geprüft werden.",
                "evidence": {"clause_key": clause_key, "character_count": len(prose.strip())},
            }
        )
    if not citations:
        findings.append(
            {
                "severity": "high",
                "title": f"{title}: keine Zitate",
                "body": "Die neueste Klausel enthält keine aufgelösten Zitate.",
                "evidence": {"clause_key": clause_key},
            }
        )
    return findings


def execute_mandate_agent_run(
    session: Session,
    *,
    mandate: Mandate,
    actor_id: int | None,
    agent_key: str,
    trigger: str = "manual",
) -> AgentRun:
    selected_keys = list(MANDATE_AGENT_KEYS) if agent_key == "all" else [agent_key]
    unknown = [key for key in selected_keys if key not in AGENT_DEFINITIONS]
    if unknown:
        raise ValueError(f"unknown agent: {', '.join(unknown)}")

    run_key = SUPERVISOR_AGENT_KEY if agent_key == "all" else agent_key
    run = AgentRun(
        mandate_id=mandate.id,
        actor_id=actor_id,
        agent_key=run_key,
        status="running",
        trigger=trigger,
        input_snapshot={
            "mandate_id": mandate.id,
            "track": mandate.track,
            "state": mandate.state,
            "selected_agents": selected_keys,
            "mode": "deterministic_supervised",
        },
    )
    session.add(run)
    session.flush()

    for key in selected_keys:
        _run_single_agent(session, mandate=mandate, run=run, agent_key=key)

    finding_count = (
        session.scalar(select(func.count()).select_from(AgentFinding).where(AgentFinding.run_id == run.id))
        or 0
    )
    action_count = (
        session.scalar(select(func.count()).select_from(AgentAction).where(AgentAction.run_id == run.id)) or 0
    )
    run.status = "completed"
    run.completed_at = datetime.now(UTC)
    run.result_summary = (
        f"{len(selected_keys)} Agenten ausgeführt, {finding_count} Findings, {action_count} Vorschläge."
    )
    session.flush()
    return run


def _run_single_agent(session: Session, *, mandate: Mandate, run: AgentRun, agent_key: str) -> None:
    if agent_key == "readiness":
        _run_readiness_agent(session, mandate=mandate, run=run)
    elif agent_key == "citation_auditor":
        _run_citation_auditor_agent(session, mandate=mandate, run=run)
    elif agent_key == "draft_qa":
        _run_draft_qa_agent(session, mandate=mandate, run=run)
    elif agent_key == "source_monitor":
        _run_source_monitor_agent(session, mandate=mandate, run=run)
    elif agent_key == "package_review":
        _run_package_review_agent(session, mandate=mandate, run=run)
    elif agent_key == "template_improvement":
        _run_template_improvement_agent(session, mandate=mandate, run=run)


def _readiness_for_mandate(session: Session, mandate: Mandate):
    sections = {
        s.section_key: s.answers
        for s in session.execute(select(IntakeSection).where(IntakeSection.mandate_id == mandate.id))
        .scalars()
        .all()
    }
    _intake_ready, intake_blockers = is_mandate_ready_for_generation(mandate.track, sections)
    uses = latest_template_uses_by_clause(session, mandate.id)
    package_blockers: list[str] = []
    if uses:
        try:
            validated_latest_template_uses(session, mandate.id)
        except ValueError as exc:
            package_blockers.append(str(exc))
    return _readiness_report(
        mandate_id=mandate.id,
        state=mandate.state,
        intake_blockers=intake_blockers,
        has_latest_uses=bool(uses),
        draft_blockers=_draft_blockers(session, uses),
        source_blockers=_source_blockers(session, uses) if uses else [],
        review_blockers=_review_blockers(session, uses),
        package_blockers=package_blockers,
    )


def _run_readiness_agent(session: Session, *, mandate: Mandate, run: AgentRun) -> None:
    report = _readiness_for_mandate(session, mandate)
    _step(
        session,
        run,
        "readiness.calculate",
        "Deterministische Gate-Prüfung ausgeführt.",
        {"next_action": report.next_action, "gates": [gate.model_dump() for gate in report.gates]},
    )
    for gate in report.gates:
        if gate.status == "blocked":
            _finding(
                session,
                run,
                mandate,
                severity="high" if gate.key in {"sources", "package"} else "medium",
                title=f"{gate.label}: blockiert",
                body=gate.summary,
                evidence={"gate": gate.key, "blockers": gate.blockers[:12]},
            )
        elif gate.status == "pending":
            _finding(
                session,
                run,
                mandate,
                severity="low",
                title=f"{gate.label}: ausstehend",
                body=gate.summary,
                evidence={"gate": gate.key},
            )
    if report.can_generate and report.gates[1].status == "pending":
        _action(
            session,
            run,
            mandate,
            action_type="generate_drafts",
            title="Entwürfe nach finaler Intake-Sichtung erzeugen",
            payload={"mandate_id": mandate.id, "requires_human_review": True},
        )
    if report.can_package:
        _action(
            session,
            run,
            mandate,
            action_type="create_package",
            title="Freigegebenes Paket nach finaler Sichtung erstellen",
            payload={"mandate_id": mandate.id, "requires_human_review": True},
        )


def _run_citation_auditor_agent(session: Session, *, mandate: Mandate, run: AgentRun) -> None:
    uses = latest_template_uses_by_clause(session, mandate.id)
    if not uses:
        _finding(
            session,
            run,
            mandate,
            severity="low",
            title="Keine Entwürfe für Zitationsprüfung",
            body="Der Citation Auditor kann erst nach der Entwurfserzeugung prüfen.",
            evidence={"mandate_id": mandate.id},
        )
        _step(session, run, "citation.no_drafts", "Keine neuesten TemplateUses gefunden.", {"uses": 0})
        return

    blockers = [*_draft_blockers(session, uses), *_source_blockers(session, uses)]
    _step(
        session,
        run,
        "citation.audit",
        "Zitate, Quellenstatus und Template-Fassung geprüft.",
        {"blockers": blockers},
    )
    if not blockers:
        _finding(
            session,
            run,
            mandate,
            severity="low",
            title="Zitationslage sauber",
            body="Die neuesten Entwürfe haben aufgelöste Zitate und keine technischen Zitationsblocker.",
            evidence={"template_use_count": len(uses)},
        )
        return
    for blocker in blockers:
        _finding(
            session,
            run,
            mandate,
            severity="high",
            title="Zitations- oder Quellenblocker",
            body=blocker,
            evidence={"agent": "citation_auditor"},
        )


def _run_draft_qa_agent(session: Session, *, mandate: Mandate, run: AgentRun) -> None:
    uses = latest_template_uses_by_clause(session, mandate.id)
    templates = _templates_by_id(session, [use.template_id for use in uses])
    count = 0
    for use in uses:
        template = templates.get(use.template_id)
        title = template.title if template else f"Klausel {use.template_id}"
        clause_key = template.clause_key if template else str(use.template_id)
        for finding in draft_quality_findings_for_clause(
            clause_key=clause_key,
            title=title,
            rendered_prose=use.rendered_prose,
            citations=use.citations,
        ):
            count += 1
            _finding(session, run, mandate, **finding)
    _step(
        session,
        run,
        "draft_qa.scan",
        "Neueste Entwürfe auf Review-Marker und Lücken geprüft.",
        {"findings": count},
    )
    if uses and count == 0:
        _finding(
            session,
            run,
            mandate,
            severity="low",
            title="Draft QA ohne Auffälligkeiten",
            body="Der deterministische Draft-QA-Scan hat keine Platzhalter- oder Zitationslücken gefunden.",
            evidence={"template_use_count": len(uses)},
        )


def _run_source_monitor_agent(session: Session, *, mandate: Mandate, run: AgentRun) -> None:
    pending_changes = (
        session.scalar(
            select(func.count())
            .select_from(AnchorChange)
            .where(AnchorChange.triage_status == TriageStatus.PENDING.value)
        )
        or 0
    )
    fetched_unverified = (
        session.scalar(
            select(func.count())
            .select_from(Anchor)
            .where(Anchor.source_status == SourceStatus.FETCHED_UNVERIFIED.value)
        )
        or 0
    )
    rejected = (
        session.scalar(
            select(func.count())
            .select_from(Anchor)
            .where(Anchor.source_status == SourceStatus.REJECTED.value)
        )
        or 0
    )
    _step(
        session,
        run,
        "source_monitor.queue",
        "Globale Quellenqueue geprüft.",
        {
            "pending_changes": pending_changes,
            "fetched_unverified": fetched_unverified,
            "rejected": rejected,
        },
    )
    if pending_changes:
        _finding(
            session,
            run,
            mandate,
            severity="high",
            title="Offene Quellenänderungen",
            body=f"{pending_changes} Quellenänderung(en) warten auf kuratorische Triage.",
            evidence={"pending_changes": pending_changes},
        )
    if fetched_unverified:
        _finding(
            session,
            run,
            mandate,
            severity="medium",
            title="Unverifizierte geladene Quellen",
            body=f"{fetched_unverified} geladene Quelle(n) warten auf Fingerprint- und Fundstellenprüfung.",
            evidence={"fetched_unverified": fetched_unverified},
        )
    if rejected:
        _finding(
            session,
            run,
            mandate,
            severity="high",
            title="Zurückgewiesene Quellen im System",
            body=f"{rejected} Quelle(n) sind zurückgewiesen und dürfen keine Freigabe tragen.",
            evidence={"rejected": rejected},
        )
    if pending_changes or fetched_unverified or rejected:
        _action(
            session,
            run,
            mandate,
            action_type="open_anchor_library",
            title="Anchor-Bibliothek kuratorisch prüfen",
            payload={"path": "/anchors", "requires_human_review": True},
        )


def _run_package_review_agent(session: Session, *, mandate: Mandate, run: AgentRun) -> None:
    report = _readiness_for_mandate(session, mandate)
    _step(session, run, "package.readiness", "Exportfähigkeit geprüft.", {"can_package": report.can_package})
    if report.can_package:
        _finding(
            session,
            run,
            mandate,
            severity="low",
            title="Exportpaket grundsätzlich bereit",
            body=(
                "Alle deterministischen Export-Gates stehen auf pass. "
                "Die finale fachliche Sichtung bleibt erforderlich."
            ),
            evidence={"mandate_id": mandate.id},
        )
        _action(
            session,
            run,
            mandate,
            action_type="create_package",
            title="Exportpaket nach finaler Sichtung erstellen",
            payload={"mandate_id": mandate.id, "requires_human_review": True},
        )
        return
    blockers = [blocker for gate in report.gates for blocker in gate.blockers]
    _finding(
        session,
        run,
        mandate,
        severity="high",
        title="Exportpaket gesperrt",
        body="Das Mandat ist noch nicht paketierbar.",
        evidence={"next_action": report.next_action, "blockers": blockers[:20]},
    )


def _run_template_improvement_agent(session: Session, *, mandate: Mandate, run: AgentRun) -> None:
    track = get_track(mandate.track)
    registry = load_registry()
    findings = 0
    if track is None:
        _finding(
            session,
            run,
            mandate,
            severity="high",
            title="Unbekannter Track",
            body=f"Für Track {mandate.track} ist keine Track-Definition registriert.",
            evidence={"track": mandate.track},
        )
        return
    for template_ref in track.templates():
        template = registry.get(mandate.track, template_ref.clause_key)
        if template is None:
            findings += 1
            _finding(
                session,
                run,
                mandate,
                severity="high",
                title=f"Template fehlt: {template_ref.clause_key}",
                body="Der Track referenziert ein Template, das im Katalog nicht vorhanden ist.",
                evidence={"clause_key": template_ref.clause_key},
            )
            continue
        if not template.anchor_refs:
            findings += 1
            _finding(
                session,
                run,
                mandate,
                severity="high",
                title=f"{template.title}: keine Anchor-Referenzen",
                body="Das Template sollte keine exportfähigen Entwürfe ohne explizite Quellenbasis erzeugen.",
                evidence={"clause_key": template.clause_key, "version": template.version},
            )
        if "[Lawyer-Review:" in template.prose_skeleton:
            findings += 1
            _finding(
                session,
                run,
                mandate,
                severity="low",
                title=f"{template.title}: Review-Hinweise im Skeleton",
                body=(
                    "Das ist für den Prototyp sinnvoll, sollte aber langfristig "
                    "in strukturierte QA-Aufgaben übersetzt werden."
                ),
                evidence={"clause_key": template.clause_key, "version": template.version},
            )
            _action(
                session,
                run,
                mandate,
                action_type="review_template",
                title=f"Template QA strukturieren: {template.title}",
                payload={
                    "track": template.track,
                    "clause_key": template.clause_key,
                    "requires_human_review": True,
                },
            )
    _step(
        session,
        run,
        "template.catalog_scan",
        "Track-Templates auf Kataloglücken geprüft.",
        {"findings": findings},
    )


def _templates_by_id(session: Session, template_ids: Iterable[int]) -> dict[int, Template]:
    ids = list(dict.fromkeys(template_ids))
    if not ids:
        return {}
    rows = session.execute(select(Template).where(Template.id.in_(ids))).scalars().all()
    return {row.id: row for row in rows}


def _step(
    session: Session,
    run: AgentRun,
    step_key: str,
    input_summary: str,
    output: dict[str, Any] | None = None,
) -> AgentStep:
    step = AgentStep(
        run_id=run.id,
        step_key=step_key,
        status="completed",
        input_summary=input_summary,
        output=output,
    )
    session.add(step)
    session.flush()
    return step


def _finding(
    session: Session,
    run: AgentRun,
    mandate: Mandate,
    *,
    severity: str,
    title: str,
    body: str,
    evidence: dict[str, Any] | None = None,
) -> AgentFinding:
    finding = AgentFinding(
        run_id=run.id,
        mandate_id=mandate.id,
        severity=severity,
        title=title,
        body=body,
        evidence=evidence,
    )
    session.add(finding)
    session.flush()
    return finding


def _action(
    session: Session,
    run: AgentRun,
    mandate: Mandate,
    *,
    action_type: str,
    title: str,
    payload: dict[str, Any] | None = None,
) -> AgentAction:
    action = AgentAction(
        run_id=run.id,
        mandate_id=mandate.id,
        action_type=action_type,
        status="proposed",
        title=title,
        payload=payload,
    )
    session.add(action)
    session.flush()
    return action
