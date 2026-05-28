"""Intake API — wizard backend.

Endpoints:
  GET  /mandates/{id}/intake               — list all sections (filled + empty)
  GET  /mandates/{id}/intake/{key}/schema  — JSON Schema for the section
  GET  /mandates/{id}/intake/{key}         — answers + validation result
  PUT  /mandates/{id}/intake/{key}         — upsert answers (validates inline)
  POST /mandates/{id}/intake/validate      — gate check across all required sections
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from micar.api.access import load_accessible_mandate_or_404
from micar.api.auth import get_current_user
from micar.compliance.audit import write_audit
from micar.intake.schema import schema_for
from micar.intake.validation import (
    is_mandate_ready_for_generation,
    is_section_complete,
    required_section_keys,
)
from micar.models import IntakeSection, session_scope
from micar.schemas import UserOut

router = APIRouter(prefix="/mandates/{mandate_id}/intake", tags=["intake"])


class SectionAnswersIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: dict[str, Any]


class SectionOut(BaseModel):
    section_key: str
    answers: dict[str, Any] | None
    is_complete: bool
    errors: list[str]
    validated_at: datetime | None


class IntakeListOut(BaseModel):
    track: str
    sections: list[SectionOut]
    is_ready_for_generation: bool
    blocking: list[str]


def _load_sections_dict(session, mandate_id: int) -> dict[str, IntakeSection]:
    rows = (
        session.execute(select(IntakeSection).where(IntakeSection.mandate_id == mandate_id)).scalars().all()
    )
    return {r.section_key: r for r in rows}


@router.get("", response_model=IntakeListOut)
def list_sections(mandate_id: int, user: UserOut = Depends(get_current_user)) -> IntakeListOut:
    with session_scope() as session:
        mandate = load_accessible_mandate_or_404(session, mandate_id, user)
        existing = _load_sections_dict(session, mandate_id)
        sections: list[SectionOut] = []
        all_keys = list(dict.fromkeys([*required_section_keys(mandate.track), *existing.keys()]))
        for key in all_keys:
            row = existing.get(key)
            answers = row.answers if row else None
            ok, errs = is_section_complete(mandate.track, key, answers)
            sections.append(
                SectionOut(
                    section_key=key,
                    answers=answers,
                    is_complete=ok,
                    errors=errs,
                    validated_at=row.validated_at if row else None,
                )
            )
        ready, blocking = is_mandate_ready_for_generation(
            mandate.track, {k: (existing.get(k).answers if existing.get(k) else None) for k in all_keys}
        )
        return IntakeListOut(
            track=mandate.track, sections=sections, is_ready_for_generation=ready, blocking=blocking
        )


@router.get("/{section_key}/schema")
def section_schema(
    mandate_id: int, section_key: str, user: UserOut = Depends(get_current_user)
) -> dict[str, Any]:
    with session_scope() as session:
        mandate = load_accessible_mandate_or_404(session, mandate_id, user)
        model = schema_for(mandate.track, section_key)
        if not model:
            raise HTTPException(status_code=404, detail="unknown section for this track")
        return model.model_json_schema()


@router.get("/{section_key}", response_model=SectionOut)
def get_section(mandate_id: int, section_key: str, user: UserOut = Depends(get_current_user)) -> SectionOut:
    with session_scope() as session:
        mandate = load_accessible_mandate_or_404(session, mandate_id, user)
        row = (
            session.execute(
                select(IntakeSection)
                .where(IntakeSection.mandate_id == mandate_id)
                .where(IntakeSection.section_key == section_key)
            )
            .scalars()
            .first()
        )
        answers = row.answers if row else None
        ok, errs = is_section_complete(mandate.track, section_key, answers)
        return SectionOut(
            section_key=section_key,
            answers=answers,
            is_complete=ok,
            errors=errs,
            validated_at=row.validated_at if row else None,
        )


@router.put("/{section_key}", response_model=SectionOut)
def upsert_section(
    mandate_id: int,
    section_key: str,
    body: SectionAnswersIn,
    user: UserOut = Depends(get_current_user),
) -> SectionOut:
    with session_scope() as session:
        mandate = load_accessible_mandate_or_404(session, mandate_id, user)
        ok, errs = is_section_complete(mandate.track, section_key, body.answers)
        # Even invalid answers are persisted — the wizard saves drafts. The
        # validation result tells the caller whether the section is complete.
        row = (
            session.execute(
                select(IntakeSection)
                .where(IntakeSection.mandate_id == mandate_id)
                .where(IntakeSection.section_key == section_key)
            )
            .scalars()
            .first()
        )
        now = datetime.now(UTC) if ok else None
        if row is None:
            row = IntakeSection(
                mandate_id=mandate_id,
                section_key=section_key,
                answers=body.answers,
                validated_at=now,
            )
            session.add(row)
        else:
            row.answers = body.answers
            row.validated_at = now
        session.flush()
        write_audit(
            session,
            kind="intake.section.upsert",
            actor_id=user.id,
            mandate_id=mandate_id,
            payload={"section_key": section_key, "is_complete": ok, "error_count": len(errs)},
        )
        return SectionOut(
            section_key=section_key,
            answers=row.answers,
            is_complete=ok,
            errors=errs,
            validated_at=row.validated_at,
        )
