"""Template registry + governance template smoke tests."""
from __future__ import annotations

from micar.templates.registry import load_registry


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
    emt = reg.for_track("emt")
    # In Phase 3 we only have CASP governance authored
    assert any(t.clause_key == "governance" for t in casp)
    assert all(t.track == "emt" for t in emt)


def test_anchor_refs_are_nonempty_for_authored_templates() -> None:
    reg = load_registry()
    for tpl in reg:
        assert tpl.anchor_refs, f"{tpl.track}/{tpl.clause_key} has no anchor_refs"
