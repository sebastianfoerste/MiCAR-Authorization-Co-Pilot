"""Audit event writer.

Single-purpose: append a row to `audit_events`. Callers redact before passing
the payload — this module does not inspect content beyond writing it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from micar.models import AuditEvent


def write_audit(
    session: Session,
    *,
    kind: str,
    actor_id: int | None = None,
    mandate_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        kind=kind,
        actor_id=actor_id,
        mandate_id=mandate_id,
        payload_redacted=payload,
    )
    session.add(event)
    session.flush()
    return event
