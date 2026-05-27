"""Shared source-change recording for anchors and affected rendered clauses."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from micar.models import Anchor, AnchorChange, TemplateUse


def record_anchor_change(
    session: Session,
    *,
    anchor: Anchor,
    prior_fingerprint: str | None,
    source_url: str,
    summary: str,
) -> AnchorChange:
    """Create a pending source review item and flag clauses citing the anchor."""
    change = AnchorChange(
        anchor_id_prev=anchor.id if prior_fingerprint else None,
        anchor_id_new=anchor.id,
        kind="amended" if prior_fingerprint else "new",
        source_url=source_url,
        summary=summary,
    )
    session.add(change)
    session.flush()

    uses = session.execute(select(TemplateUse)).scalars().all()
    for use in uses:
        citations = use.citations or []
        if any(
            isinstance(citation, dict) and citation.get("anchor_id") == anchor.id
            for citation in citations
        ):
            use.flagged_by_change_id = change.id
    return change
