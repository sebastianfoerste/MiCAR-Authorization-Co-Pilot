"""Resolve free-text citation strings to anchor IDs.

The renderer (and lawyers writing template YAML) speaks the canonical citation
form. The resolver matches against the `citation_canonical` column with
moderate normalization (whitespace, common abbreviation variants).

This is *deliberately conservative*. A miss returns None — the calling code
hard-fails the template render. We do not fuzzy-match to "probably this
anchor" because the wrong anchor is worse than no anchor in a regulatory
filing.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from micar.models import Anchor

# Map common abbreviation variants to the canonical form used in rendering.
_NORMALIZATIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bArtikel\b", re.IGNORECASE), "Art."),
    (re.compile(r"\bAbsatz\b", re.IGNORECASE), "Abs."),
    (re.compile(r"\bNummer\b", re.IGNORECASE), "Nr."),
    (re.compile(r"\bRandnummer\b", re.IGNORECASE), "Rn."),
    (re.compile(r"\s+"), " "),
]


def normalize(citation: str) -> str:
    out = citation.strip()
    for pattern, repl in _NORMALIZATIONS:
        out = pattern.sub(repl, out)
    return out.strip()


def resolve_exact(session: Session, citation: str, *, version: str | None = None) -> Anchor | None:
    """Exact match by normalized canonical form. Returns None on miss."""
    target = normalize(citation)
    stmt = select(Anchor).where(Anchor.citation_canonical == target)
    if version is not None:
        stmt = stmt.where(Anchor.version == version)
    return session.execute(stmt).scalars().first()


def resolve_many(session: Session, citations: Iterable[str]) -> dict[str, Anchor | None]:
    """Resolve multiple citations in one round-trip. Misses appear as None.

    Caller is responsible for treating any None as a hard error in the
    citation-verification pass.
    """
    citations = [normalize(c) for c in citations]
    if not citations:
        return {}
    stmt = select(Anchor).where(Anchor.citation_canonical.in_(citations))
    by_citation: dict[str, Anchor] = {
        a.citation_canonical: a for a in session.execute(stmt).scalars().all()
    }
    return {c: by_citation.get(c) for c in citations}
