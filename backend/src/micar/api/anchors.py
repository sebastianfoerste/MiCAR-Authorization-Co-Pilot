"""Anchor browser and curator-controlled source verification API."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import or_, select

from micar.anchors.changes import record_anchor_change
from micar.api.auth import get_current_user
from micar.compliance.audit import write_audit
from micar.models import (
    Anchor,
    AnchorAuthority,
    AnchorChange,
    SourceStatus,
    TriageStatus,
    UserRole,
    session_scope,
)
from micar.schemas import UserOut

router = APIRouter(prefix="/anchors", tags=["anchors"])


class AnchorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    level: str
    authority: str
    citation_canonical: str
    url: str | None
    version: str
    effective_from: datetime | None
    effective_to: datetime | None
    title_or_excerpt: str | None
    binding_force_note: str | None
    source_fingerprint: str | None
    source_status: str
    source_retrieved_at: datetime | None
    reviewed_at: datetime | None
    review_note: str | None


class AnchorListOut(BaseModel):
    items: list[AnchorOut]
    total: int


class AnchorSourceOut(AnchorOut):
    body: str | None
    body_char_count: int


class AnchorVerifyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_fingerprint: str = Field(min_length=64, max_length=128)
    review_note: str = Field(min_length=20, max_length=2000)

    @field_validator("review_note")
    @classmethod
    def normalize_review_note(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 20:
            raise ValueError("review_note must document the source review")
        return cleaned


class AnchorSourceTextIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_url: str = Field(pattern=r"^https://", max_length=1024)
    source_text: str = Field(min_length=20)
    version: str = Field(min_length=1, max_length=64)


class AnchorChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    anchor_id_prev: int | None
    anchor_id_new: int | None
    kind: str
    detected_at: datetime
    source_url: str | None
    summary: str | None
    triage_status: str
    approved_by: int | None
    approved_at: datetime | None


class AnchorChangeTriageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["rejected"]


def _to_out(a: Anchor) -> AnchorOut:
    excerpt: str | None = None
    if a.body:
        excerpt = a.body[:280] + ("…" if len(a.body) > 280 else "")
    return AnchorOut(
        id=a.id,
        level=a.level,
        authority=a.authority,
        citation_canonical=a.citation_canonical,
        url=a.url,
        version=a.version,
        effective_from=a.effective_from,
        effective_to=a.effective_to,
        title_or_excerpt=excerpt,
        binding_force_note=a.binding_force_note,
        source_fingerprint=a.source_fingerprint,
        source_status=a.source_status,
        source_retrieved_at=a.source_retrieved_at,
        reviewed_at=a.reviewed_at,
        review_note=a.review_note,
    )


def _to_source_out(a: Anchor) -> AnchorSourceOut:
    return AnchorSourceOut(
        **_to_out(a).model_dump(),
        body=a.body,
        body_char_count=len(a.body or ""),
    )


def _require_curator(user: UserOut) -> None:
    if user.role not in {UserRole.CURATOR.value, UserRole.ADMIN.value}:
        raise HTTPException(status_code=403, detail="curator role required")


@router.get("", response_model=AnchorListOut)
def list_anchors(
    _user: UserOut = Depends(get_current_user),
    q: str | None = Query(None, description="full-text fragment to match in citation or body"),
    level: str | None = None,
    authority: str | None = None,
    source_status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> AnchorListOut:
    with session_scope() as session:
        stmt = select(Anchor)
        count_stmt = select(Anchor)

        if level:
            stmt = stmt.where(Anchor.level == level)
            count_stmt = count_stmt.where(Anchor.level == level)
        if authority:
            stmt = stmt.where(Anchor.authority == authority)
            count_stmt = count_stmt.where(Anchor.authority == authority)
        if source_status:
            stmt = stmt.where(Anchor.source_status == source_status)
            count_stmt = count_stmt.where(Anchor.source_status == source_status)
        if q:
            needle = f"%{q.strip()}%"
            stmt = stmt.where(or_(Anchor.citation_canonical.ilike(needle), Anchor.body.ilike(needle)))
            count_stmt = count_stmt.where(
                or_(Anchor.citation_canonical.ilike(needle), Anchor.body.ilike(needle))
            )

        total = len(session.execute(count_stmt).scalars().all())
        rows = (
            session.execute(
                stmt.order_by(Anchor.authority, Anchor.citation_canonical).limit(limit).offset(offset)
            )
            .scalars()
            .all()
        )
        return AnchorListOut(items=[_to_out(r) for r in rows], total=total)


@router.get("/changes", response_model=list[AnchorChangeOut])
def list_anchor_changes(
    _user: UserOut = Depends(get_current_user),
    triage_status: str | None = Query(TriageStatus.PENDING.value),
) -> list[AnchorChangeOut]:
    with session_scope() as session:
        stmt = select(AnchorChange)
        if triage_status:
            stmt = stmt.where(AnchorChange.triage_status == triage_status)
        rows = session.execute(stmt.order_by(AnchorChange.detected_at.desc())).scalars().all()
        return [AnchorChangeOut.model_validate(row) for row in rows]


@router.get("/{anchor_id}", response_model=AnchorOut)
def get_anchor(anchor_id: int, _user: UserOut = Depends(get_current_user)) -> AnchorOut:
    with session_scope() as session:
        row = session.get(Anchor, anchor_id)
        if not row:
            raise HTTPException(status_code=404, detail="anchor not found")
        return _to_out(row)


@router.get("/{anchor_id}/source", response_model=AnchorSourceOut)
def get_anchor_source(anchor_id: int, user: UserOut = Depends(get_current_user)) -> AnchorSourceOut:
    _require_curator(user)
    with session_scope() as session:
        row = session.get(Anchor, anchor_id)
        if not row:
            raise HTTPException(status_code=404, detail="anchor not found")
        return _to_source_out(row)


@router.post("/{anchor_id}/source-text", response_model=AnchorOut)
def ingest_public_source_text(
    anchor_id: int,
    body: AnchorSourceTextIn,
    user: UserOut = Depends(get_current_user),
) -> AnchorOut:
    """Store curator-supplied public source text for supplementary anchors."""
    _require_curator(user)
    source_text = body.source_text.strip()
    fingerprint = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    with session_scope() as session:
        row = session.get(Anchor, anchor_id)
        if row is None:
            raise HTTPException(status_code=404, detail="anchor not found")
        if row.authority == AnchorAuthority.EU_REG.value:
            raise HTTPException(
                status_code=409,
                detail="EU regulation text must be refreshed through the official ingest command",
            )

        prior_fingerprint = row.source_fingerprint
        changed = prior_fingerprint != fingerprint
        row.url = body.source_url
        row.body = source_text
        row.version = body.version
        row.source_fingerprint = fingerprint
        row.source_retrieved_at = datetime.now(UTC)

        change_id: int | None = None
        if changed:
            row.source_status = SourceStatus.FETCHED_UNVERIFIED.value
            row.reviewed_at = None
            row.reviewed_by = None
            row.review_note = None
            change = record_anchor_change(
                session,
                anchor=row,
                prior_fingerprint=prior_fingerprint,
                source_url=body.source_url,
                summary="Public source text fingerprint requires curator verification.",
            )
            change_id = change.id
        elif row.source_status != SourceStatus.VERIFIED.value:
            row.source_status = SourceStatus.FETCHED_UNVERIFIED.value
            row.review_note = None

        write_audit(
            session,
            kind="anchor.source.ingested",
            actor_id=user.id,
            payload={
                "anchor_id": row.id,
                "source_url": body.source_url,
                "source_fingerprint": fingerprint,
                "change_id": change_id,
            },
        )
        return _to_out(row)


@router.post("/{anchor_id}/verify", response_model=AnchorOut)
def verify_anchor(
    anchor_id: int,
    body: AnchorVerifyIn,
    user: UserOut = Depends(get_current_user),
) -> AnchorOut:
    _require_curator(user)
    with session_scope() as session:
        row = session.get(Anchor, anchor_id)
        if row is None:
            raise HTTPException(status_code=404, detail="anchor not found")
        if not row.body or not row.source_fingerprint:
            raise HTTPException(status_code=409, detail="official source text has not been fetched")
        if row.source_fingerprint != body.expected_fingerprint:
            raise HTTPException(status_code=409, detail="source fingerprint changed; refresh review")
        row.source_status = SourceStatus.VERIFIED.value
        row.reviewed_at = datetime.now(UTC)
        row.reviewed_by = user.id
        row.review_note = body.review_note
        pending_changes = (
            session.execute(
                select(AnchorChange)
                .where(AnchorChange.anchor_id_new == row.id)
                .where(AnchorChange.triage_status == TriageStatus.PENDING.value)
            )
            .scalars()
            .all()
        )
        for change in pending_changes:
            change.triage_status = TriageStatus.APPROVED.value
            change.approved_by = user.id
            change.approved_at = row.reviewed_at
        write_audit(
            session,
            kind="anchor.source.verified",
            actor_id=user.id,
            payload={
                "anchor_id": row.id,
                "source_fingerprint": row.source_fingerprint,
                "review_note": body.review_note,
            },
        )
        return _to_out(row)


@router.post("/changes/{change_id}/triage", response_model=AnchorChangeOut)
def triage_anchor_change(
    change_id: int,
    body: AnchorChangeTriageIn,
    user: UserOut = Depends(get_current_user),
) -> AnchorChangeOut:
    _require_curator(user)
    with session_scope() as session:
        change = session.get(AnchorChange, change_id)
        if change is None:
            raise HTTPException(status_code=404, detail="anchor change not found")
        if body.decision == "rejected":
            change.triage_status = TriageStatus.REJECTED.value
            change.approved_by = user.id
            change.approved_at = datetime.now(UTC)
            if change.anchor_id_new:
                anchor = session.get(Anchor, change.anchor_id_new)
                if anchor:
                    anchor.source_status = SourceStatus.REJECTED.value
                    anchor.reviewed_at = change.approved_at
                    anchor.reviewed_by = user.id
                    anchor.review_note = None
        write_audit(
            session,
            kind="anchor.change.rejected",
            actor_id=user.id,
            payload={"change_id": change.id, "anchor_id": change.anchor_id_new},
        )
        return AnchorChangeOut.model_validate(change)
