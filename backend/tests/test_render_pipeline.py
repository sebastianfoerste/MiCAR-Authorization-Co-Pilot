"""End-to-end pipeline test in stub mode, against a hermetic in-memory setup.

We don't need a live Postgres for this — the renderer accepts a SQLAlchemy
Session-shaped object, the stub synthesizer is deterministic, and the
citation verifier works in-process. We exercise the full flow:

  template + facts + anchors → synthesize (stub) → citation_check → RenderOutcome.

The full render_template() call needs a real Session because it persists a
TemplateUse. We isolate the *logic* by directly composing the pieces.
"""

from __future__ import annotations

from datetime import date

from micar.intake.schema import EntitySection, GovernanceSection
from micar.models import Anchor
from micar.synthesis.client import SynthesisInput, synthesize
from micar.templates.registry import load_registry
from micar.verification.citation_check import verify_against_set


def _make_anchor(citation: str) -> Anchor:
    a = Anchor()
    a.id = abs(hash(citation)) % 100000
    a.citation_canonical = citation
    a.effective_from = date(2024, 12, 30)
    a.effective_to = None
    a.level = "level_1"
    a.authority = "eu_regulation"
    a.version = "2023-06-09"
    return a


def test_governance_renders_and_passes_citation_check() -> None:
    # 1. Template
    reg = load_registry()
    template = reg.get("casp", "governance")
    assert template is not None

    # 2. Facts
    entity = EntitySection(
        legal_name="Cobalt Crypto GmbH",
        legal_form="GmbH",
        registered_office="Hamburg",
        place_of_central_admin="Hamburg",
        contact_person_name="A. Beispiel",
        contact_person_email="a@cobalt.example",
    )
    governance = GovernanceSection(
        management_body_members=2,
        management_body_qualifications="MD A: 12y FinReg; MD B: 9y Compliance.",
        supervisory_body_present=False,
        fit_and_proper_assessment_done=True,
        organisational_structure_chart_attached=True,
        three_lines_of_defence=True,
    )
    facts = {
        "entity": entity.model_dump(mode="json"),
        "governance": governance.model_dump(mode="json"),
        "_mandate": {"id": 1, "name": "Project Cobalt", "track": "casp"},
    }

    # 3. Anchors — provide the template's referenced anchors so the
    #    citation_check has something to resolve.
    anchor_lookup = {c: _make_anchor(c) for c in template.anchor_refs}

    # 4. Stub synthesis
    rendered = synthesize(
        SynthesisInput(
            track="casp",
            clause_key="governance",
            template_title=template.title,
            template_skeleton=template.prose_skeleton,
            template_anchor_refs=template.anchor_refs,
            facts=facts,
            anchors_for_prompt=[
                {"citation": c, "body_or_title": "", "binding_force_note": ""} for c in template.anchor_refs
            ],
        )
    )

    # 5. Substitutions worked — entity name lands in the prose
    assert "Cobalt Crypto GmbH" in rendered.prose
    assert "2 Mitgliedern" in rendered.prose
    assert "Hamburg" in rendered.prose

    # 6. The stub returns the template anchors as citations, and the verifier
    #    accepts them.
    check = verify_against_set(
        citations=rendered.citations,
        anchor_lookup=anchor_lookup,
        ref_date=date(2026, 5, 20),
    )
    assert check.ok, (check.missing, check.out_of_effect)
    assert set(check.resolved.keys()) == set(template.anchor_refs)


def test_render_fails_when_template_anchor_unknown() -> None:
    # Author a synthetic template with a citation that does not exist in the
    # anchor universe. Verify the check returns ok=False.
    check = verify_against_set(
        citations=["Art. 999 VO (EU) 2023/1114 (MiCAR)"],
        anchor_lookup={},
        ref_date=date(2026, 5, 20),
    )
    assert not check.ok
    assert "Art. 999 VO (EU) 2023/1114 (MiCAR)" in check.missing


def test_docx_smoke(tmp_path) -> None:
    """One DOCX writes to disk and is non-empty."""
    from micar.artifacts.docx import ClauseInput, render_package_docx

    out = tmp_path / "package.docx"
    render_package_docx(
        out,
        mandate_name="Project Cobalt",
        track="casp",
        clauses=[
            ClauseInput(
                clause_key="governance",
                title="Governance-Konzept",
                prose="## 1. Geschäftsleitung\n\nDer Antragsteller verfügt über 2 Geschäftsleiter.",
                citations=["Art. 68 VO (EU) 2023/1114 (MiCAR)"],
            )
        ],
        version=1,
    )
    assert out.exists()
    assert out.stat().st_size > 5000  # python-docx produces a real Office Open XML file
