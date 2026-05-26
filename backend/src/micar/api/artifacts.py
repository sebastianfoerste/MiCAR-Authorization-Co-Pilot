"""Artifact endpoints — trigger render, list, download.

Current surface:
  POST /mandates/{id}/render          — render every template applicable to the
                                        mandate; return per-template results.
  POST /mandates/{id}/package         — assemble a downloadable zip of all
                                        TemplateUses produced so far.
  GET  /mandates/{id}/artifacts       — list artifacts.
  GET  /artifacts/{id}/download       — stream the file.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from micar.api.access import load_accessible_mandate_or_404
from micar.api.auth import get_current_user
from micar.artifacts.package import build_package
from micar.compliance.audit import write_audit
from micar.intake.schema import CASPServiceCode
from micar.models import (
    Anchor,
    Artifact,
    Mandate,
    MandateState,
    Template,
    TemplateUse,
    session_scope,
)
from micar.schemas import UserOut
from micar.templates.registry import TemplateDef, load_registry
from micar.templates.renderer import RenderOutcome, render_template
from micar.tracks.registry import get_track

router = APIRouter(tags=["artifacts"])


class RenderResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    clause_key: str
    template_version: str
    ok: bool
    template_use_id: int | None
    citation_problems: list[str]
    template_anchor_problems: list[str]
    error: str | None
    prose_preview: str | None


class RenderRunOut(BaseModel):
    total: int
    ok: int
    failed: int
    results: list[RenderResult]


class PackageOut(BaseModel):
    artifact_id: int
    download_path: str
    sha256: str
    total_clauses: int
    flagged_clauses: int


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    mandate_id: int
    kind: str
    format: str
    file_path: str
    version: int
    sha256: str | None
    created_at: str


class CitationProvenanceOut(BaseModel):
    citation: str
    anchor_id: int | None
    source_status: str | None
    url: str | None


class ReviewUseOut(BaseModel):
    id: int
    clause_key: str
    title: str
    template_version: str
    lawyer_review_status: str
    flagged_by_change_id: int | None
    rendered_prose: str | None
    rendered_at: datetime | None
    citations: list[CitationProvenanceOut]


class ReviewDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]


class ReviewDecisionOut(BaseModel):
    template_use_id: int
    lawyer_review_status: str


def _applicable_templates(mandate: Mandate, services: list[str]) -> list[TemplateDef]:
    track = get_track(mandate.track)
    if not track:
        return []
    registry = load_registry()
    out: list[TemplateDef] = []
    for tref in track.templates():
        td = registry.get(mandate.track, tref.clause_key)
        if td is None:
            continue  # Template not yet authored
        # Apply conditional service filters from the in-yaml definition AND
        # from the track ref (the track ref is the source of truth for now).
        cond = list(tref.conditional_on_services) or td.conditional_on_services
        if cond and not any(c in services for c in cond):
            continue
        out.append(td)
    return out


def _selected_services(session, mandate_id: int) -> list[str]:
    from micar.models import IntakeSection

    row = (
        session.execute(
            select(IntakeSection)
            .where(IntakeSection.mandate_id == mandate_id)
            .where(IntakeSection.section_key == "services_offered")
        )
        .scalars()
        .first()
    )
    if row is None or not row.answers:
        return []
    answers = row.answers
    services = answers.get("services") if isinstance(answers, dict) else None
    if not services:
        return []
    return [s.value if isinstance(s, CASPServiceCode) else str(s) for s in services]


def _outcome_to_result(template: TemplateDef, outcome: RenderOutcome) -> RenderResult:
    cit_problems: list[str] = []
    if outcome.citation_check.missing:
        cit_problems.extend([f"missing: {m}" for m in outcome.citation_check.missing])
    if outcome.citation_check.out_of_effect:
        cit_problems.extend([f"out_of_effect: {o}" for o in outcome.citation_check.out_of_effect])

    preview: str | None = None
    if outcome.rendered:
        preview = outcome.rendered.prose[:400]
    return RenderResult(
        clause_key=template.clause_key,
        template_version=template.version,
        ok=outcome.ok,
        template_use_id=outcome.template_use_id,
        citation_problems=cit_problems,
        template_anchor_problems=outcome.template_anchor_problems,
        error=outcome.error,
        prose_preview=preview,
    )


def _latest_template_uses(session, mandate_id: int) -> list[TemplateUse]:
    rows = (
        session.execute(
            select(TemplateUse)
            .where(TemplateUse.mandate_id == mandate_id)
            .order_by(TemplateUse.id.desc())
        )
        .scalars()
        .all()
    )
    latest: dict[int, TemplateUse] = {}
    for row in rows:
        latest.setdefault(row.template_id, row)
    return sorted(latest.values(), key=lambda row: row.id)


def _review_use_out(session, use: TemplateUse) -> ReviewUseOut:
    template = session.get(Template, use.template_id)
    citations = use.citations or []
    anchor_ids = [entry.get("anchor_id") for entry in citations if entry.get("anchor_id")]
    anchors = (
        session.execute(select(Anchor).where(Anchor.id.in_(anchor_ids))).scalars().all()
        if anchor_ids
        else []
    )
    by_id = {anchor.id: anchor for anchor in anchors}
    return ReviewUseOut(
        id=use.id,
        clause_key=template.clause_key if template else str(use.template_id),
        title=template.title if template else f"Klausel {use.template_id}",
        template_version=use.template_version,
        lawyer_review_status=use.lawyer_review_status,
        flagged_by_change_id=use.flagged_by_change_id,
        rendered_prose=use.rendered_prose,
        rendered_at=use.rendered_at,
        citations=[
            CitationProvenanceOut(
                citation=entry.get("citation", ""),
                anchor_id=entry.get("anchor_id"),
                source_status=(
                    by_id[entry["anchor_id"]].source_status
                    if entry.get("anchor_id") in by_id
                    else None
                ),
                url=(
                    by_id[entry["anchor_id"]].url
                    if entry.get("anchor_id") in by_id
                    else None
                ),
            )
            for entry in citations
        ],
    )


@router.post("/mandates/{mandate_id}/render", response_model=RenderRunOut)
def render_mandate(
    mandate_id: int, user: UserOut = Depends(get_current_user)
) -> RenderRunOut:
    with session_scope() as session:
        m = load_accessible_mandate_or_404(session, mandate_id, user)
        if m.state not in {MandateState.READY_TO_GENERATE.value, MandateState.IN_REVIEW.value}:
            raise HTTPException(
                status_code=409,
                detail=f"mandate state '{m.state}' is not eligible for render",
            )
        services = _selected_services(session, mandate_id)
        templates = _applicable_templates(m, services)

        results: list[RenderResult] = []
        ok_count = 0
        for td in templates:
            outcome = render_template(session, mandate=m, template=td, actor_id=user.id)
            results.append(_outcome_to_result(td, outcome))
            ok_count += int(outcome.ok)

        # State transition: any success → GENERATED; pure failure leaves state.
        if ok_count:
            m.state = MandateState.GENERATED.value
        return RenderRunOut(total=len(results), ok=ok_count, failed=len(results) - ok_count, results=results)


@router.get("/mandates/{mandate_id}/renders", response_model=list[ReviewUseOut])
def list_rendered_clauses(
    mandate_id: int, user: UserOut = Depends(get_current_user)
) -> list[ReviewUseOut]:
    with session_scope() as session:
        load_accessible_mandate_or_404(session, mandate_id, user)
        return [_review_use_out(session, use) for use in _latest_template_uses(session, mandate_id)]


@router.post(
    "/mandates/{mandate_id}/renders/{template_use_id}/review",
    response_model=ReviewDecisionOut,
)
def review_rendered_clause(
    mandate_id: int,
    template_use_id: int,
    body: ReviewDecisionIn,
    user: UserOut = Depends(get_current_user),
) -> ReviewDecisionOut:
    with session_scope() as session:
        load_accessible_mandate_or_404(session, mandate_id, user)
        use = session.get(TemplateUse, template_use_id)
        if use is None or use.mandate_id != mandate_id:
            raise HTTPException(status_code=404, detail="rendered clause not found")
        latest_ids = {row.id for row in _latest_template_uses(session, mandate_id)}
        if use.id not in latest_ids:
            raise HTTPException(status_code=409, detail="only latest clause versions can be reviewed")
        if body.decision == "approved" and use.lawyer_review_status == "citation_failed":
            raise HTTPException(status_code=409, detail="citation-failed clause cannot be approved")
        if body.decision == "approved" and use.flagged_by_change_id is not None:
            raise HTTPException(status_code=409, detail="source-changed clause must be regenerated")
        if body.decision == "approved":
            anchor_ids = {
                entry.get("anchor_id")
                for entry in (use.citations or [])
                if entry.get("anchor_id") is not None
            }
            anchors = (
                session.execute(select(Anchor).where(Anchor.id.in_(anchor_ids))).scalars().all()
                if anchor_ids
                else []
            )
            if not anchor_ids or len(anchors) != len(anchor_ids) or any(
                anchor.source_status != "verified" for anchor in anchors
            ):
                raise HTTPException(
                    status_code=409,
                    detail="all cited sources must be verified before approval",
                )
        use.lawyer_review_status = body.decision
        write_audit(
            session,
            kind="render.clause.reviewed",
            actor_id=user.id,
            mandate_id=mandate_id,
            payload={"template_use_id": use.id, "decision": body.decision},
        )
        return ReviewDecisionOut(
            template_use_id=use.id, lawyer_review_status=use.lawyer_review_status
        )


@router.post("/mandates/{mandate_id}/package", response_model=PackageOut)
def package_mandate(
    mandate_id: int, user: UserOut = Depends(get_current_user)
) -> PackageOut:
    with session_scope() as session:
        m = load_accessible_mandate_or_404(session, mandate_id, user)
        try:
            result = build_package(session, mandate=m)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return PackageOut(
            artifact_id=result.artifact_id,
            download_path=f"/artifacts/{result.artifact_id}/download",
            sha256=result.sha256,
            total_clauses=result.total_clauses,
            flagged_clauses=result.flagged_clauses,
        )


@router.get("/mandates/{mandate_id}/artifacts", response_model=list[ArtifactOut])
def list_artifacts(
    mandate_id: int, user: UserOut = Depends(get_current_user)
) -> list[ArtifactOut]:
    with session_scope() as session:
        load_accessible_mandate_or_404(session, mandate_id, user)
        rows = (
            session.execute(
                select(Artifact)
                .where(Artifact.mandate_id == mandate_id)
                .order_by(Artifact.created_at.desc())
            )
            .scalars()
            .all()
        )
        return [
            ArtifactOut(
                id=r.id,
                mandate_id=r.mandate_id,
                kind=r.kind,
                format=r.format,
                file_path=r.file_path,
                version=r.version,
                sha256=r.sha256,
                created_at=r.created_at.isoformat(),
            )
            for r in rows
        ]


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(
    artifact_id: int, user: UserOut = Depends(get_current_user)
):
    with session_scope() as session:
        row = session.get(Artifact, artifact_id)
        if not row:
            raise HTTPException(status_code=404, detail="artifact not found")
        load_accessible_mandate_or_404(session, row.mandate_id, user)
        path = Path(row.file_path)
        if not path.exists():
            raise HTTPException(status_code=410, detail="artifact file missing on disk")
        media = "application/zip" if row.format == "zip" else "application/octet-stream"
        return FileResponse(str(path), media_type=media, filename=path.name)
