"""Citation-verifier tests — locks the hard-fail behaviour without a live DB."""
from __future__ import annotations

from datetime import date

from micar.models import Anchor
from micar.verification.citation_check import verify_against_set


def _anchor(id_: int, citation: str, eff_from: date | None, eff_to: date | None = None) -> Anchor:
    a = Anchor()
    a.id = id_
    a.citation_canonical = citation
    a.effective_from = eff_from
    a.effective_to = eff_to
    a.level = "level_1"
    a.authority = "eu_regulation"
    a.version = "1"
    return a


def test_empty_citations_passes() -> None:
    res = verify_against_set(citations=[], anchor_lookup={}, ref_date=date(2026, 5, 20))
    assert res.ok
    assert not res.missing


def test_resolves_known_citation() -> None:
    anchor = _anchor(1, "Art. 68 VO (EU) 2023/1114 (MiCAR)", date(2024, 12, 30))
    lookup = {anchor.citation_canonical: anchor}
    res = verify_against_set(
        citations=["Art. 68 VO (EU) 2023/1114 (MiCAR)"],
        anchor_lookup=lookup,
        ref_date=date(2026, 5, 20),
    )
    assert res.ok
    assert res.resolved == {"Art. 68 VO (EU) 2023/1114 (MiCAR)": 1}


def test_normalizes_before_lookup() -> None:
    anchor = _anchor(1, "Art. 68 VO (EU) 2023/1114 (MiCAR)", date(2024, 12, 30))
    lookup = {anchor.citation_canonical: anchor}
    res = verify_against_set(
        citations=["Artikel 68 VO (EU) 2023/1114 (MiCAR)"],
        anchor_lookup=lookup,
        ref_date=date(2026, 5, 20),
    )
    assert res.ok, (res.missing, res.out_of_effect)


def test_hallucinated_citation_hard_fails() -> None:
    lookup = {
        "Art. 68 VO (EU) 2023/1114 (MiCAR)": _anchor(
            1, "Art. 68 VO (EU) 2023/1114 (MiCAR)", date(2024, 12, 30)
        )
    }
    res = verify_against_set(
        citations=["Art. 999 VO (EU) 2023/1114 (MiCAR)"],
        anchor_lookup=lookup,
        ref_date=date(2026, 5, 20),
    )
    assert not res.ok
    assert "Art. 999 VO (EU) 2023/1114 (MiCAR)" in res.missing


def test_anchor_not_yet_effective_fails() -> None:
    anchor = _anchor(1, "Art. 99 VO (EU) 2023/1114 (MiCAR)", date(2030, 1, 1))
    lookup = {anchor.citation_canonical: anchor}
    res = verify_against_set(
        citations=["Art. 99 VO (EU) 2023/1114 (MiCAR)"],
        anchor_lookup=lookup,
        ref_date=date(2026, 5, 20),
    )
    assert not res.ok
    assert "Art. 99 VO (EU) 2023/1114 (MiCAR)" in res.out_of_effect


def test_anchor_expired_fails() -> None:
    anchor = _anchor(
        1,
        "Art. 50 VO (EU) 2023/1114 (MiCAR)",
        eff_from=date(2024, 1, 1),
        eff_to=date(2025, 1, 1),
    )
    lookup = {anchor.citation_canonical: anchor}
    res = verify_against_set(
        citations=["Art. 50 VO (EU) 2023/1114 (MiCAR)"],
        anchor_lookup=lookup,
        ref_date=date(2026, 5, 20),
    )
    assert not res.ok
    assert "Art. 50 VO (EU) 2023/1114 (MiCAR)" in res.out_of_effect


def test_multiple_problems_collected() -> None:
    lookup = {
        "Art. 68 VO (EU) 2023/1114 (MiCAR)": _anchor(
            1, "Art. 68 VO (EU) 2023/1114 (MiCAR)", date(2024, 12, 30)
        )
    }
    res = verify_against_set(
        citations=[
            "Art. 68 VO (EU) 2023/1114 (MiCAR)",
            "Art. 999 VO (EU) 2023/1114 (MiCAR)",
        ],
        anchor_lookup=lookup,
        ref_date=date(2026, 5, 20),
    )
    assert not res.ok
    assert res.missing == ["Art. 999 VO (EU) 2023/1114 (MiCAR)"]
    msg = res.hard_error_message()
    assert "missing" in msg
