"""Mandate CRUD + state transitions."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from micar.api.access import load_accessible_mandate_or_404
from micar.api.auth import get_current_user
from micar.artifacts.package import (
    latest_template_uses_by_clause,
    template_version_problem,
    validated_latest_template_uses,
)
from micar.compliance.audit import write_audit
from micar.intake.validation import is_mandate_ready_for_generation
from micar.models import Anchor, IntakeSection, Mandate, MandateState, Track, UserRole, session_scope
from micar.schemas import MandateOut, UserOut
from micar.tracks.registry import all_tracks, get_track

router = APIRouter(prefix="/mandates", tags=["mandates"])


class MandateCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    client_label: str | None = None
    track: str = Field(pattern=r"^(casp|emt|art)$")
    target_filing_date: date | None = None
    redact_client_identifiers: bool = True


class TrackOut(BaseModel):
    code: str
    label_de: str
    required_section_keys: list[str]


class TransitionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to_state: str


class ReadinessGateOut(BaseModel):
    key: str
    label: str
    status: Literal["pass", "pending", "blocked"]
    summary: str
    blockers: list[str]


class MandateReadinessOut(BaseModel):
    mandate_id: int
    state: str
    next_action: str
    can_generate: bool
    can_enter_review: bool
    can_package: bool
    gates: list[ReadinessGateOut]


def _load_user_id(session: Session, email: str) -> int | None:
    from micar.models import User

    return session.execute(select(User.id).where(User.email == email.lower().strip())).scalar_one_or_none()


def _gate(
    key: str,
    label: str,
    *,
    blockers: list[str],
    pass_summary: str,
    pending_summary: str,
    blocked_summary: str,
    pending: bool = False,
) -> ReadinessGateOut:
    if blockers:
        return ReadinessGateOut(
            key=key,
            label=label,
            status="blocked",
            summary=blocked_summary,
            blockers=blockers,
        )
    if pending:
        return ReadinessGateOut(
            key=key,
            label=label,
            status="pending",
            summary=pending_summary,
            blockers=[],
        )
    return ReadinessGateOut(
        key=key,
        label=label,
        status="pass",
        summary=pass_summary,
        blockers=[],
    )


def _next_action(gates: list[ReadinessGateOut]) -> str:
    for gate in gates:
        if gate.status == "blocked":
            return {
                "intake": "Intake vervollständigen",
                "drafts": "Entwürfe reparieren oder neu erzeugen",
                "sources": "Quellen prüfen und verifizieren",
                "review": "Klauseln anwaltlich prüfen und freigeben",
                "package": "Exportblocker beheben",
            }[gate.key]
        if gate.status == "pending":
            return {
                "drafts": "Entwürfe erzeugen",
                "sources": "Zitations- und Quellenlage nach Entwurf prüfen",
                "review": "Klauseln in Prüfung geben",
                "package": "Freigegebene Klauseln paketieren",
            }.get(gate.key, "Weiter bearbeiten")
    return "Freigegebenes Paket erstellen"


def _readiness_report(
    *,
    mandate_id: int,
    state: str,
    intake_blockers: list[str],
    has_latest_uses: bool,
    draft_blockers: list[str],
    source_blockers: list[str],
    review_blockers: list[str],
    package_blockers: list[str],
) -> MandateReadinessOut:
    gates = [
        _gate(
            "intake",
            "Intake",
            blockers=intake_blockers,
            pass_summary="Alle erforderlichen Intake-Sektionen sind vollständig.",
            pending_summary="Intake noch nicht bewertet.",
            blocked_summary="Pflichtangaben fehlen oder validieren nicht.",
        ),
        _gate(
            "drafts",
            "Entwürfe",
            blockers=draft_blockers,
            pass_summary="Aktuelle Entwürfe liegen ohne technische Render-Blocker vor.",
            pending_summary="Noch keine Entwürfe erzeugt.",
            blocked_summary="Entwürfe müssen repariert oder neu erzeugt werden.",
            pending=not has_latest_uses,
        ),
        _gate(
            "sources",
            "Quellen",
            blockers=source_blockers,
            pass_summary="Alle zitierten Quellen sind verifiziert.",
            pending_summary="Quellenprüfung startet nach der Entwurfserzeugung.",
            blocked_summary="Nicht alle zitierten Quellen sind verifiziert.",
            pending=not has_latest_uses,
        ),
        _gate(
            "review",
            "Anwaltliche Prüfung",
            blockers=review_blockers,
            pass_summary="Alle neuesten Klauseln sind freigegeben.",
            pending_summary="Klauseln warten auf Review.",
            blocked_summary="Mindestens eine Klausel ist nicht freigegeben.",
            pending=not has_latest_uses,
        ),
        _gate(
            "package",
            "Exportpaket",
            blockers=package_blockers,
            pass_summary="Das Mandat ist paketierbar.",
            pending_summary="Export ist erst nach Entwurf und Review relevant.",
            blocked_summary="Export ist gesperrt.",
            pending=not has_latest_uses,
        ),
    ]
    return MandateReadinessOut(
        mandate_id=mandate_id,
        state=state,
        next_action=_next_action(gates),
        can_generate=not intake_blockers,
        can_enter_review=has_latest_uses and not draft_blockers,
        can_package=all(gate.status == "pass" for gate in gates),
        gates=gates,
    )


def _draft_blockers(session: Session, uses) -> list[str]:
    blockers: list[str] = []
    for use in uses:
        version_problem = template_version_problem(session, use)
        if version_problem:
            blockers.append(f"Klausel {use.id}: Template-Fassung veraltet ({version_problem})")
        if use.flagged_by_change_id is not None:
            blockers.append(f"Klausel {use.id}: Quellenänderung {use.flagged_by_change_id} offen")
        if use.lawyer_review_status == "citation_failed":
            blockers.append(f"Klausel {use.id}: Zitationsprüfung fehlgeschlagen")
    return blockers


def _source_blockers(session: Session, uses) -> list[str]:
    blockers: list[str] = []
    citations = [entry for use in uses for entry in (use.citations or [])]
    if not citations:
        return ["Keine aufgelösten Zitate in den neuesten Entwürfen."]

    anchor_ids = {entry.get("anchor_id") for entry in citations if entry.get("anchor_id") is not None}
    anchors = (
        session.execute(select(Anchor).where(Anchor.id.in_(anchor_ids))).scalars().all() if anchor_ids else []
    )
    anchors_by_id = {anchor.id: anchor for anchor in anchors}
    for entry in citations:
        citation = entry.get("citation") or "Unbenannte Quelle"
        anchor_id = entry.get("anchor_id")
        if anchor_id is None:
            blockers.append(f"{citation}: kein Anchor aufgelöst")
            continue
        anchor = anchors_by_id.get(anchor_id)
        if anchor is None:
            blockers.append(f"{citation}: Anchor nicht gefunden")
        elif anchor.source_status != "verified":
            blockers.append(f"{citation}: Quellenstatus {anchor.source_status}")
    return blockers


def _review_blockers(session: Session, uses) -> list[str]:
    blockers: list[str] = []
    for use in uses:
        version_problem = template_version_problem(session, use)
        if version_problem:
            blockers.append(f"Klausel {use.id}: Template-Fassung veraltet ({version_problem})")
        if use.flagged_by_change_id is not None:
            blockers.append(f"Klausel {use.id}: Quellenänderung {use.flagged_by_change_id} offen")
        if use.lawyer_review_status != "approved":
            blockers.append(f"Klausel {use.id}: Review-Status {use.lawyer_review_status}")
    return blockers


@router.get("/tracks", response_model=list[TrackOut])
def list_tracks(_user: UserOut = Depends(get_current_user)) -> list[TrackOut]:
    return [
        TrackOut(code=t.code, label_de=t.label_de, required_section_keys=list(t.required_section_keys))
        for t in all_tracks()
    ]


@router.get("", response_model=list[MandateOut])
def list_mandates(user: UserOut = Depends(get_current_user)) -> list[MandateOut]:
    with session_scope() as session:
        stmt = select(Mandate)
        if user.role != UserRole.ADMIN.value:
            stmt = stmt.where(Mandate.owner_id == user.id)
        rows = session.execute(stmt.order_by(Mandate.created_at.desc())).scalars().all()
        return [MandateOut.model_validate(r) for r in rows]


@router.post("", response_model=MandateOut, status_code=201)
def create_mandate(body: MandateCreateIn, user: UserOut = Depends(get_current_user)) -> MandateOut:
    if get_track(body.track) is None:
        raise HTTPException(status_code=400, detail=f"unknown track: {body.track}")
    with session_scope() as session:
        owner_id = _load_user_id(session, user.email)
        m = Mandate(
            name=body.name,
            client_label=body.client_label,
            track=body.track,
            state=MandateState.DRAFT.value if body.track == Track.CASP else MandateState.DRAFT.value,
            target_filing_date=body.target_filing_date,
            redact_client_identifiers=body.redact_client_identifiers,
            owner_id=owner_id,
        )
        session.add(m)
        session.flush()
        write_audit(
            session,
            kind="mandate.create",
            actor_id=owner_id,
            mandate_id=m.id,
            payload={"track": body.track},
        )
        return MandateOut.model_validate(m)


@router.get("/{mandate_id}", response_model=MandateOut)
def get_mandate(mandate_id: int, user: UserOut = Depends(get_current_user)) -> MandateOut:
    with session_scope() as session:
        m = load_accessible_mandate_or_404(session, mandate_id, user)
        return MandateOut.model_validate(m)


@router.get("/{mandate_id}/readiness", response_model=MandateReadinessOut)
def get_mandate_readiness(mandate_id: int, user: UserOut = Depends(get_current_user)) -> MandateReadinessOut:
    with session_scope() as session:
        m = load_accessible_mandate_or_404(session, mandate_id, user)
        sections = {
            s.section_key: s.answers
            for s in session.execute(select(IntakeSection).where(IntakeSection.mandate_id == mandate_id))
            .scalars()
            .all()
        }
        _intake_ready, intake_blockers = is_mandate_ready_for_generation(m.track, sections)
        uses = latest_template_uses_by_clause(session, mandate_id)
        package_blockers: list[str] = []
        if uses:
            try:
                validated_latest_template_uses(session, m.id)
            except ValueError as exc:
                package_blockers.append(str(exc))
        return _readiness_report(
            mandate_id=m.id,
            state=m.state,
            intake_blockers=intake_blockers,
            has_latest_uses=bool(uses),
            draft_blockers=_draft_blockers(session, uses),
            source_blockers=_source_blockers(session, uses) if uses else [],
            review_blockers=_review_blockers(session, uses),
            package_blockers=package_blockers,
        )


_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    MandateState.DRAFT.value: {MandateState.INTAKE.value},
    MandateState.INTAKE.value: {MandateState.DRAFT.value, MandateState.READY_TO_GENERATE.value},
    MandateState.READY_TO_GENERATE.value: {
        MandateState.INTAKE.value,
        MandateState.GENERATED.value,
    },
    MandateState.GENERATED.value: {MandateState.IN_REVIEW.value},
    MandateState.IN_REVIEW.value: {
        MandateState.READY_TO_GENERATE.value,
        MandateState.APPROVED.value,
    },
    MandateState.APPROVED.value: {MandateState.FILED.value},
}


@router.post("/{mandate_id}/transition", response_model=MandateOut)
def transition(mandate_id: int, body: TransitionIn, user: UserOut = Depends(get_current_user)) -> MandateOut:
    with session_scope() as session:
        m = load_accessible_mandate_or_404(session, mandate_id, user)
        allowed = _ALLOWED_TRANSITIONS.get(m.state, set())
        if body.to_state not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"transition {m.state} -> {body.to_state} not allowed",
            )
        # READY_TO_GENERATE gate: every required section must validate.
        if body.to_state == MandateState.READY_TO_GENERATE.value:
            sections = {
                s.section_key: s.answers
                for s in session.execute(select(IntakeSection).where(IntakeSection.mandate_id == mandate_id))
                .scalars()
                .all()
            }
            ok, blocking = is_mandate_ready_for_generation(m.track, sections)
            if not ok:
                raise HTTPException(
                    status_code=409,
                    detail={"reason": "intake_incomplete", "blocking": blocking},
                )
        if body.to_state == MandateState.APPROVED.value:
            try:
                validated_latest_template_uses(session, m.id)
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        m.state = body.to_state
        owner_id = _load_user_id(session, user.email)
        write_audit(
            session,
            kind="mandate.transition",
            actor_id=owner_id,
            mandate_id=m.id,
            payload={"to_state": body.to_state},
        )
        return MandateOut.model_validate(m)
