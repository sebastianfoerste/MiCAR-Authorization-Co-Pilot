"""Template registry + governance template smoke tests."""

from __future__ import annotations

from micar.anchors.seed_external import eba_micar_guideline_anchors
from micar.anchors.seed_level2 import all_level2
from micar.templates.registry import load_registry
from micar.tracks.registry import all_tracks


def test_governance_template_loads() -> None:
    reg = load_registry()
    gov = reg.get("casp", "governance")
    assert gov is not None
    assert gov.title.startswith("Governance-Konzept")
    assert "Art. 68 VO (EU) 2023/1114 (MiCAR)" in gov.anchor_refs
    assert set(gov.required_sections) == {"entity", "governance"}


def test_registry_for_track_filters_correctly() -> None:
    reg = load_registry()
    casp = reg.for_track("casp")
    art = reg.for_track("art")
    emt = reg.for_track("emt")
    assert len(casp) == 9
    assert len(art) == 6
    assert len(emt) == 7
    assert any(t.clause_key == "governance" for t in casp)
    assert any(t.clause_key == "reserve_policy_art" for t in art)
    assert any(t.clause_key == "liquidity_management_policy_art" for t in art)
    assert any(t.clause_key == "investment_of_funds_emt" for t in emt)
    assert any(t.clause_key == "liquidity_management_policy_emt" for t in emt)
    assert any(t.clause_key == "recovery_plan_emt" for t in emt)
    assert any(t.clause_key == "redemption_plan_emt" for t in emt)


def test_every_declared_track_document_has_authored_template() -> None:
    reg = load_registry()
    missing = [
        f"{track.code}/{template.clause_key}"
        for track in all_tracks()
        for template in track.templates()
        if reg.get(track.code, template.clause_key) is None
    ]
    assert not missing, missing


def test_anchor_refs_are_nonempty_for_authored_templates() -> None:
    reg = load_registry()
    for tpl in reg:
        assert tpl.anchor_refs, f"{tpl.track}/{tpl.clause_key} has no anchor_refs"


def test_level2_template_references_are_registered_official_sources() -> None:
    reg = load_registry()
    known_level2 = {anchor.citation_canonical for anchor in all_level2()}
    referenced_level2 = {ref for template in reg for ref in template.anchor_refs if "MiCAR-" in ref}
    casp_application = reg.get("casp", "authorization_application")
    casp_market_abuse = reg.get("casp", "market_abuse")
    art_application = reg.get("art", "authorization_application_art")
    art_liquidity = reg.get("art", "liquidity_management_policy_art")
    emt_whitepaper = reg.get("emt", "whitepaper_emt")
    emt_liquidity = reg.get("emt", "liquidity_management_policy_emt")

    assert referenced_level2 == known_level2
    assert casp_application is not None
    assert casp_market_abuse is not None
    assert art_application is not None
    assert art_liquidity is not None
    assert emt_whitepaper is not None
    assert emt_liquidity is not None
    assert "VO (EU) 2025/305 (MiCAR-CASP-Antrags-RTS)" in casp_application.anchor_refs
    assert "VO (EU) 2025/885 (MiCAR-Marktmissbrauch-RTS)" in casp_market_abuse.anchor_refs
    assert "VO (EU) 2025/1125 (MiCAR-ART-Antrags-RTS)" in art_application.anchor_refs
    assert "VO (EU) 2025/1264 (MiCAR-Liquiditätsmanagement-RTS)" in art_liquidity.anchor_refs
    assert "VO (EU) 2024/2984 (MiCAR-Whitepaper-ITS)" in emt_whitepaper.anchor_refs
    assert "VO (EU) 2025/1264 (MiCAR-Liquiditätsmanagement-RTS)" in emt_liquidity.anchor_refs


def test_level3_template_references_are_registered_official_guidelines() -> None:
    reg = load_registry()
    known = {anchor.citation_canonical for anchor in eba_micar_guideline_anchors()}
    required = {
        ref
        for template in reg
        for ref in template.anchor_refs
        if ref.startswith("EBA, Leitlinien") or ref.startswith("EBA/ESMA, Leitlinien")
    }

    assert required == known
