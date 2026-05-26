"""Artifact endpoints — trigger render, list, download.

Phase 3 surface:
  POST /mandates/{id}/render          — render every template applicable to the
                                        mandate; return per-template results.
  POST /mandates/{id}/package         — assemble a downloadable zip of all
                                        TemplateUses produced so far.
  GET  /mandates/{id}/artifacts       — list artifacts.
  GET  /artifacts/{id}/download       — stream the file.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from micar.api.access import load_accessible_mandate_or_404
from micar.api.auth import get_current_user
from micar.artifacts.package import build_package
from micar.intake.schema import CASPServiceCode
from micar.models import Artifact, Mandate, MandateState, session_scope
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
