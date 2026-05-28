"""Deterministic citation verification — the legal-quality gate.

A synthesized clause is acceptable only if every citation it references:
  1. Exists in the `anchors` table (exact canonical match after normalization).
  2. Is currently effective at the mandate's reference date — i.e.,
     anchor.effective_from <= ref_date AND (effective_to IS NULL OR effective_to > ref_date).

Anything else fails the render hard. The renderer surfaces the failure as a
red row in the artifacts UI. We never silently swap to a near-match; the wrong
anchor in a filing is worse than no anchor.

The API stays in-memory friendly: pass an iterable of
Anchor rows alongside the citations. The renderer module fetches the anchor
universe once per render and feeds it in.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from micar.anchors.resolver import normalize, resolve_many
from micar.models import Anchor


@dataclass(frozen=True)
class CitationCheckResult:
    ok: bool
    missing: list[str]
    out_of_effect: list[str]
    resolved: dict[str, int]  # normalized citation -> anchor_id

    def hard_error_message(self) -> str:
        problems: list[str] = []
        if self.missing:
            problems.append("missing: " + ", ".join(self.missing))
        if self.out_of_effect:
            problems.append("not currently effective: " + ", ".join(self.out_of_effect))
        return "; ".join(problems) if problems else ""


def _is_in_effect(anchor: Anchor, ref_date: date) -> bool:
    if anchor.effective_from is None:
        return True
    if anchor.effective_from > ref_date:
        return False
    return not (anchor.effective_to is not None and anchor.effective_to <= ref_date)


def verify_citations(
    session: Session,
    *,
    citations: Iterable[str],
    ref_date: date,
) -> CitationCheckResult:
    """Resolve every citation; classify into ok / missing / out-of-effect."""
    citation_list = [normalize(c) for c in citations]
    if not citation_list:
        return CitationCheckResult(ok=True, missing=[], out_of_effect=[], resolved={})
    resolved_anchors = resolve_many(session, citation_list)

    missing: list[str] = []
    out_of_effect: list[str] = []
    resolved_ids: dict[str, int] = {}
    for cit, anchor in resolved_anchors.items():
        if anchor is None:
            missing.append(cit)
            continue
        if not _is_in_effect(anchor, ref_date):
            out_of_effect.append(cit)
            continue
        resolved_ids[cit] = anchor.id
    ok = not missing and not out_of_effect
    return CitationCheckResult(ok=ok, missing=missing, out_of_effect=out_of_effect, resolved=resolved_ids)


def verify_against_set(
    *,
    citations: Iterable[str],
    anchor_lookup: dict[str, Anchor],
    ref_date: date,
) -> CitationCheckResult:
    """In-process variant — used by tests and by the renderer once it has
    pre-fetched the anchor universe.
    """
    citation_list = [normalize(c) for c in citations]
    if not citation_list:
        return CitationCheckResult(ok=True, missing=[], out_of_effect=[], resolved={})
    missing: list[str] = []
    out_of_effect: list[str] = []
    resolved_ids: dict[str, int] = {}
    for cit in citation_list:
        anchor = anchor_lookup.get(cit)
        if anchor is None:
            missing.append(cit)
            continue
        if not _is_in_effect(anchor, ref_date):
            out_of_effect.append(cit)
            continue
        resolved_ids[cit] = anchor.id
    ok = not missing and not out_of_effect
    return CitationCheckResult(ok=ok, missing=missing, out_of_effect=out_of_effect, resolved=resolved_ids)
