"""Administrator-only read access to the redacted operational audit trail."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from micar.api.auth import get_current_user
from micar.models import AuditEvent, UserRole, session_scope
from micar.schemas import UserOut

router = APIRouter(prefix="/audit-events", tags=["audit"])


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: int | None
    mandate_id: int | None
    kind: str
    payload_redacted: dict[str, Any] | None
    occurred_at: datetime


class AuditEventListOut(BaseModel):
    items: list[AuditEventOut]
    total: int


def _require_admin(user: UserOut) -> None:
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="admin role required")


@router.get("", response_model=AuditEventListOut)
def list_audit_events(
    user: UserOut = Depends(get_current_user),
    kind: str | None = None,
    mandate_id: int | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> AuditEventListOut:
    _require_admin(user)
    with session_scope() as session:
        stmt = select(AuditEvent)
        count_stmt = select(func.count()).select_from(AuditEvent)
        if kind:
            stmt = stmt.where(AuditEvent.kind == kind)
            count_stmt = count_stmt.where(AuditEvent.kind == kind)
        if mandate_id is not None:
            stmt = stmt.where(AuditEvent.mandate_id == mandate_id)
            count_stmt = count_stmt.where(AuditEvent.mandate_id == mandate_id)
        rows = (
            session.execute(
                stmt.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(limit).offset(offset)
            )
            .scalars()
            .all()
        )
        total = session.execute(count_stmt).scalar_one()
        return AuditEventListOut(
            items=[AuditEventOut.model_validate(row) for row in rows],
            total=total,
        )
