"""Mandate CRUD + state transitions."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from micar.api.access import load_accessible_mandate_or_404
from micar.api.auth import get_current_user
from micar.compliance.audit import write_audit
from micar.intake.validation import is_mandate_ready_for_generation
from micar.models import IntakeSection, Mandate, MandateState, Track, UserRole, session_scope
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


def _load_user_id(session: Session, email: str) -> int | None:
    from micar.models import User

    return session.execute(
        select(User.id).where(User.email == email.lower().strip())
    ).scalar_one_or_none()


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
def transition(
    mandate_id: int, body: TransitionIn, user: UserOut = Depends(get_current_user)
) -> MandateOut:
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
                for s in session.execute(
                    select(IntakeSection).where(IntakeSection.mandate_id == mandate_id)
                )
                .scalars()
                .all()
            }
            ok, blocking = is_mandate_ready_for_generation(m.track, sections)
            if not ok:
                raise HTTPException(
                    status_code=409,
                    detail={"reason": "intake_incomplete", "blocking": blocking},
                )
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
