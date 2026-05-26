"""Composer: template + intake facts + anchors → RenderedClause → TemplateUse.

Calling sequence (per template, per mandate):

  1. Load template from registry.
  2. Gather intake facts for required_sections.
  3. Fetch each anchor referenced in template.anchor_refs from DB. If any
     anchor is missing, hard-fail before even calling the LLM — that is a
     template authoring error, not a render error.
  4. Run the synthesis client (stub or real Anthropic).
  5. Run citation_check on the LLM's citations.
  6. Persist TemplateUse with rendered prose + cited anchor ids + status.

The renderer never decides "close enough" — it succeeds iff every anchor
exists, is in effect at the mandate's reference date, and the LLM produced a
non-empty prose body.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from micar.anchors.resolver import normalize
from micar.compliance.audit import write_audit
from micar.config import get_settings
from micar.intake.schema import schema_for
from micar.models import Anchor, IntakeSection, Mandate, SourceStatus, Template, TemplateUse
from micar.synthesis.client import (
    RenderedClause,
    SynthesisInput,
    external_synthesis_enabled,
    synthesize,
)
from micar.synthesis.redaction import RedactedFacts, redact_facts
from micar.templates.registry import TemplateDef
from micar.verification.citation_check import (
    CitationCheckResult,
    verify_against_set,
)


@dataclass
class RenderOutcome:
    template_use_id: int | None
    rendered: RenderedClause | None
    citation_check: CitationCheckResult
    template_anchor_problems: list[str]
    error: str | None = None

    @property
    def ok(self) -> bool:
        return (
            self.error is None
            and self.rendered is not None
            and self.citation_check.ok
            and not self.template_anchor_problems
        )


def _fetch_template_anchors(
    session: Session, citations: list[str]
) -> dict[str, Anchor]:
    if not citations:
        return {}
    normalized = [normalize(c) for c in citations]
    rows = (
        session.execute(select(Anchor).where(Anchor.citation_canonical.in_(normalized)))
        .scalars()
        .all()
    )
    return {a.citation_canonical: a for a in rows}


def _facts_for_template(
    session: Session, mandate: Mandate, template: TemplateDef
) -> dict[str, Any]:
    """Merge required intake sections into one fact dict, validating against
    their Pydantic models. Any failure surfaces as a structured error in the
    RenderOutcome.
    """
    facts: dict[str, Any] = {"_mandate": {"id": mandate.id, "name": mandate.name, "track": mandate.track}}
    section_rows = (
        session.execute(select(IntakeSection).where(IntakeSection.mandate_id == mandate.id))
        .scalars()
        .all()
    )
    by_key = {r.section_key: r for r in section_rows}
    for key in template.required_sections:
        row = by_key.get(key)
        if row is None or row.answers is None:
            raise ValueError(f"intake section missing: {key}")
        model = schema_for(mandate.track, key)
        if model is None:
            raise ValueError(f"intake schema for {mandate.track}/{key} not registered")
        facts[key] = model.model_validate(row.answers).model_dump(mode="json")
    return facts


def _upsert_template_row(session: Session, template: TemplateDef) -> Template:
    row = session.execute(
        select(Template).where(
            Template.track == template.track,
            Template.clause_key == template.clause_key,
            Template.version == template.version,
        )
    ).scalar_one_or_none()
    values = {
        "title": template.title,
        "anchor_refs": template.anchor_refs,
        "facts_schema": {"required_sections": template.required_sections},
        "prose_skeleton": template.prose_skeleton,
    }
    if row is None:
        row = Template(
            track=template.track,
            clause_key=template.clause_key,
            version=template.version,
            **values,
        )
        session.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    session.flush()
    return row


def _omitted_required_citations(
    template: TemplateDef, rendered_citations: list[str]
) -> list[str]:
    normalized_rendered = {normalize(citation) for citation in rendered_citations}
    return [
        citation
        for citation in template.anchor_refs
        if normalize(citation) not in normalized_rendered
    ]


def _blocked_outcome(
    session: Session,
    *,
    mandate: Mandate,
    actor_id: int | None,
    template: TemplateDef,
    template_anchor_problems: list[str],
    error: str,
) -> RenderOutcome:
    write_audit(
        session,
        kind="render.template.blocked",
        actor_id=actor_id,
        mandate_id=mandate.id,
        payload={
            "clause_key": template.clause_key,
            "template_version": template.version,
            "reason": error,
        },
    )
    return RenderOutcome(
        template_use_id=None,
        rendered=None,
        citation_check=CitationCheckResult(ok=False, missing=[], out_of_effect=[], resolved={}),
        template_anchor_problems=template_anchor_problems,
        error=error,
    )


def render_template(
    session: Session,
    *,
    mandate: Mandate,
    template: TemplateDef,
    actor_id: int | None = None,
    ref_date: date | None = None,
) -> RenderOutcome:
    """Run one template render end-to-end, persisting the TemplateUse row."""
    ref = ref_date or datetime.now(UTC).date()

    # 1. Pre-flight: every anchor referenced by the template must exist + be in effect.
    anchor_lookup = _fetch_template_anchors(session, template.anchor_refs)
    template_anchor_pre = verify_against_set(
        citations=template.anchor_refs, anchor_lookup=anchor_lookup, ref_date=ref
    )
    template_anchor_problems: list[str] = []
    if not template_anchor_pre.ok:
        template_anchor_problems = (
            [f"missing: {m}" for m in template_anchor_pre.missing]
            + [f"out_of_effect: {o}" for o in template_anchor_pre.out_of_effect]
        )
        return _blocked_outcome(
            session,
            mandate=mandate,
            actor_id=actor_id,
            template=template,
            template_anchor_problems=template_anchor_problems,
            error="required template anchor is missing or out of effect",
        )

    # 2. Intake facts
    try:
        facts = _facts_for_template(session, mandate, template)
    except ValueError as exc:
        return _blocked_outcome(
            session,
            mandate=mandate,
            actor_id=actor_id,
            template=template,
            template_anchor_problems=template_anchor_problems,
            error=str(exc),
        )

    external = external_synthesis_enabled()
    if external:
        unverified = [
            citation
            for citation, anchor in anchor_lookup.items()
            if anchor.source_status != SourceStatus.VERIFIED.value
        ]
        if unverified:
            problems = [*template_anchor_problems, *[f"unverified_source: {c}" for c in unverified]]
            return _blocked_outcome(
                session,
                mandate=mandate,
                actor_id=actor_id,
                template=template,
                template_anchor_problems=problems,
                error="external synthesis requires curator-verified source text",
            )

    # 3. Build anchors_for_prompt only from anchors that resolved.
    anchors_for_prompt = [
        {
            "citation": a.citation_canonical,
            "body_or_title": (a.body or "") or "",
            "binding_force_note": a.binding_force_note or "",
        }
        for a in anchor_lookup.values()
    ]
    settings = get_settings()
    redacted: RedactedFacts | None = None
    synthesis_facts = facts
    redaction_mode = "local_stub"
    if external and (
        mandate.redact_client_identifiers or not settings.allow_unredacted_external_client_data
    ):
        redacted = redact_facts(facts)
        synthesis_facts = redacted.facts
        redaction_mode = "redacted"
    elif external:
        redaction_mode = "approved_unredacted"

    payload = SynthesisInput(
        track=mandate.track,
        clause_key=template.clause_key,
        template_title=template.title,
        template_skeleton=template.prose_skeleton,
        template_anchor_refs=template.anchor_refs,
        facts=synthesis_facts,
        anchors_for_prompt=anchors_for_prompt,
    )

    # 4. Synthesize
    rendered = synthesize(payload)
    if redacted is not None:
        rendered.prose = redacted.restore(rendered.prose)

    # 5. Verify citations the LLM actually produced.
    final_check = verify_against_set(
        citations=rendered.citations, anchor_lookup=anchor_lookup, ref_date=ref
    )
    omitted_required_citations = _omitted_required_citations(template, rendered.citations)
    template_anchor_problems.extend(
        f"omitted_required_citation: {citation}" for citation in omitted_required_citations
    )

    # 6. Persist TemplateUse — record the result whether ok or not. A failed
    #    render is still a row so the UI can show it as a red entry.
    persisted_id: int | None = None
    template_row = _upsert_template_row(session, template)
    run_id = uuid.uuid4().hex
    use = TemplateUse(
        mandate_id=mandate.id,
        template_id=template_row.id,
        template_version=template.version,
        facts_snapshot=facts,
        rendered_prose=rendered.prose,
        citations=[
            {
                "citation": cit,
                "anchor_id": final_check.resolved.get(normalize(cit)),
            }
            for cit in rendered.citations
        ],
        llm_run_id=run_id,
        lawyer_review_status=(
            "pending" if final_check.ok and not template_anchor_problems else "citation_failed"
        ),
        rendered_at=datetime.now(UTC),
    )
    session.add(use)
    session.flush()
    persisted_id = use.id

    write_audit(
        session,
        kind="render.template",
        actor_id=actor_id,
        mandate_id=mandate.id,
        payload={
            "clause_key": template.clause_key,
            "template_version": template.version,
            "citation_check_ok": final_check.ok,
            "template_anchor_problems": template_anchor_problems,
            "model": rendered.model,
            "llm_run_id": run_id,
            "external_processing": external,
            "redaction_mode": redaction_mode,
        },
    )

    return RenderOutcome(
        template_use_id=persisted_id,
        rendered=rendered,
        citation_check=final_check,
        template_anchor_problems=template_anchor_problems,
        error=None,
    )
