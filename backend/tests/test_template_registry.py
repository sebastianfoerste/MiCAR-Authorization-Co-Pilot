"""Template registry + governance template smoke tests."""
from __future__ import annotations

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
    assert len(art) == 5
    assert len(emt) == 4
    assert any(t.clause_key == "governance" for t in casp)
    assert any(t.clause_key == "reserve_policy_art" for t in art)
    assert any(t.clause_key == "investment_of_funds_emt" for t in emt)


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
