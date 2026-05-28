"""Synthesis client — Anthropic + instructor, BRAO-aware.

Two operating modes:

  * real    — only when ANTHROPIC_API_KEY is set and external processing has
              been explicitly enabled after the required approval.
  * stub    — deterministic fallback for dev + tests. Returns the template's
              prose skeleton with simple Jinja-style fact substitution and
              the template's own anchor_refs as citations.

The stub mode is what makes the full pipeline runnable end-to-end without an
LLM call — so lawyers can wire up templates locally before any spend, and
tests stay hermetic. When the real LLM lands, the same RenderedClause shape
flows through.

Redaction is prepared by the renderer before external processing and restored
locally after receipt.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from micar.config import get_settings

log = logging.getLogger(__name__)


class RenderedClause(BaseModel):
    """LLM (or stub) output for one template render."""

    prose: str = Field(min_length=1)
    citations: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    model: str = ""


@dataclass(frozen=True)
class SynthesisInput:
    track: str
    clause_key: str
    template_title: str
    template_skeleton: str
    template_anchor_refs: list[str]
    facts: dict[str, Any]
    anchors_for_prompt: list[dict[str, str]]
    """[{citation, body_or_title, binding_force_note}, ...]"""


SYSTEM_PROMPT = """\
Du bist ein Berater des gunnercooke-Teams. Du unterstützt beim Entwurf einer
MiCAR-Antragsschrift. Sprache: Deutsch, Sie-Form, Gutachtenstil wo angemessen.

Regeln:
  - Zitate ausschließlich aus der gelieferten Anchor-Liste. Erfinde nichts.
  - Jede Zitation in der Ausgabe wortgleich zur "citation"-Spalte aus der Liste.
  - Keine Floskeln, keine Anglizismen, kein Marketing-Ton.
  - Risiko-Vokabular kalibriert: "unproblematisch / vertretbar / erhebliches
    Risiko / nicht vertretbar"; wenn der Fakt-Stand das nicht hergibt, bleib
    sachlich und nenne den fehlenden Tatsachenstand.
  - Wenn das Skeleton einen Platzhalter "[Hier füllt das gunnercooke-Team ...]"
    enthält, ersetze ihn durch konkrete Aussagen aus den facts und Anchors.
    Wenn das nicht möglich ist, lasse den Platzhalter und ergänze in notes.
"""


def _lookup_dotted(d: dict[str, Any], path: str) -> Any | None:
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _render_stub(payload: SynthesisInput) -> RenderedClause:
    """Deterministic placeholder. Fact substitution only, without fabrication."""

    def render_value(value: Any) -> str:
        if isinstance(value, bool):
            return "ja" if value else "nein"
        if isinstance(value, list):
            return ", ".join(str(item) for item in value) if value else "keine"
        return str(value)

    def sub(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        value = _lookup_dotted(payload.facts, key)
        if value is None:
            return match.group(0)
        return render_value(value)

    body = re.sub(r"\{\{\s*fact:([a-zA-Z0-9_.]+)\s*\}\}", sub, payload.template_skeleton)

    settings = get_settings()
    reason = (
        "Externe Verarbeitung nicht freigegeben."
        if settings.anthropic_api_key.get_secret_value()
        else "ANTHROPIC_API_KEY nicht gesetzt."
    )
    notes = [
        f"Stub-Renderer aktiv ({reason}) Keine LLM-Synthese.",
        "Anchors aus dem Template wurden 1:1 als Zitate übernommen.",
    ]
    if not body.strip():
        body = f"## {payload.template_title}\n\n[Lawyer-Author erforderlich: Skeleton ist leer.]"

    return RenderedClause(
        prose=body,
        citations=list(payload.template_anchor_refs),
        notes=notes,
        model="stub",
    )


def _render_real(payload: SynthesisInput) -> RenderedClause:
    """Anthropic + instructor synthesis. Lazy import so tests don't need keys."""
    import instructor
    from anthropic import Anthropic

    settings = get_settings()
    client = instructor.from_anthropic(Anthropic(api_key=settings.anthropic_api_key.get_secret_value()))

    user_payload = _build_user_message(payload)
    log.info(
        "llm.synthesize",
        extra={"clause_key": payload.clause_key, "model": settings.llm_model_synthesis},
    )

    rendered: RenderedClause = client.messages.create(
        model=settings.llm_model_synthesis,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_payload}],
        response_model=RenderedClause,
    )
    rendered.model = settings.llm_model_synthesis
    return rendered


def _build_user_message(payload: SynthesisInput) -> str:
    import json

    anchors_block = "\n\n".join(
        (
            f"- citation: {a['citation']}\n"
            f"  body_or_title: {a.get('body_or_title', 'keine Angabe')}\n"
            f"  binding: {a.get('binding_force_note', 'keine Angabe')}"
        )
        for a in payload.anchors_for_prompt
    )
    facts_block = json.dumps(payload.facts, indent=2, ensure_ascii=False)
    return (
        f"Track: {payload.track}\n"
        f"Clause: {payload.clause_key}: {payload.template_title}\n\n"
        f"Anchors (use only these, verbatim):\n{anchors_block}\n\n"
        f"Facts (JSON):\n{facts_block}\n\n"
        f"Skeleton to fill in:\n---\n{payload.template_skeleton}\n---\n\n"
        f"Erzeuge die Klausel als RenderedClause."
    )


def synthesize(payload: SynthesisInput) -> RenderedClause:
    settings = get_settings()
    if not settings.anthropic_api_key.get_secret_value() or not settings.external_llm_processing_enabled:
        return _render_stub(payload)
    return _render_real(payload)


def external_synthesis_enabled() -> bool:
    settings = get_settings()
    return bool(settings.anthropic_api_key.get_secret_value() and settings.external_llm_processing_enabled)
