"""Anchor browser and curator-controlled source verification API."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select

from micar.api.auth import get_current_user
from micar.compliance.audit import write_audit
from micar.models import Anchor, SourceStatus, UserRole, session_scope
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


class AnchorListOut(BaseModel):
    items: list[AnchorOut]
    total: int


class AnchorVerifyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_fingerprint: str = Field(min_length=64, max_length=128)


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
    )


@router.get("", response_model=AnchorListOut)
def list_anchors(
    _user: UserOut = Depends(get_current_user),
    q: str | None = Query(None, description="full-text fragment to match in citation or body"),
    level: str | None = None,
    authority: str | None = None,
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
        if q:
            needle = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(Anchor.citation_canonical.ilike(needle), Anchor.body.ilike(needle))
            )
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


@router.get("/{anchor_id}", response_model=AnchorOut)
def get_anchor(
    anchor_id: int, _user: UserOut = Depends(get_current_user)
) -> AnchorOut:
    with session_scope() as session:
        row = session.get(Anchor, anchor_id)
        if not row:
            raise HTTPException(status_code=404, detail="anchor not found")
        return _to_out(row)


@router.post("/{anchor_id}/verify", response_model=AnchorOut)
def verify_anchor(
    anchor_id: int,
    body: AnchorVerifyIn,
    user: UserOut = Depends(get_current_user),
) -> AnchorOut:
    if user.role not in {UserRole.CURATOR.value, UserRole.ADMIN.value}:
        raise HTTPException(status_code=403, detail="curator role required")
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
        write_audit(
            session,
            kind="anchor.source.verified",
            actor_id=user.id,
            payload={"anchor_id": row.id, "source_fingerprint": row.source_fingerprint},
        )
        return _to_out(row)
