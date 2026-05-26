"""Citation rendering tests — locks in the legal-voice.md examples."""
from __future__ import annotations

from micar.anchors.citation import (
    BaFinMerkblattParts,
    BaFinRundschreibenParts,
    ESMACitationParts,
    EUCitationParts,
    GermanLawParts,
    render_citation,
)
from micar.anchors.resolver import normalize


def test_micar_article_basic() -> None:
    out = render_citation(
        EUCitationParts(instrument_number="2023/1114", instrument_kind="VO", article=16, absatz=1)
    )
    assert out == "Art. 16 Abs. 1 VO (EU) 2023/1114 (MiCAR)"


def test_micar_article_with_satz_nr_lit() -> None:
    out = render_citation(
        EUCitationParts(
            instrument_number="2023/1114",
            instrument_kind="VO",
            article=68,
            absatz=2,
            satz=1,
            nr=3,
            lit="a",
        )
    )
    assert out == "Art. 68 Abs. 2 Satz 1 Nr. 3 lit. a VO (EU) 2023/1114 (MiCAR)"


def test_recital() -> None:
    out = render_citation(
        EUCitationParts(instrument_number="2023/1114", instrument_kind="VO", recital=11)
    )
    assert out == "Erwägungsgrund 11 MiCAR"


def test_dsa_example_from_legal_voice() -> None:
    # legal-voice.md example: "Art. 74 Abs. 1 VO (EU) 2022/2065 v. 19.10.2022 (DSA)..."
    # Our renderer omits the date — that lives on the Anchor row (effective_from).
    out = render_citation(
        EUCitationParts(instrument_number="2022/2065", instrument_kind="VO", article=74, absatz=1)
    )
    assert out == "Art. 74 Abs. 1 VO (EU) 2022/2065 (DSA)"


def test_esma_qa() -> None:
    out = render_citation(
        ESMACitationParts(
            document_label="Q&A on MiCAR",
            document_id="ESMA75-453128700-1340",
            version=3,
            date="15.7.2025",
            question="Question 4.1",
        )
    )
    assert (
        out == "ESMA, Q&A on MiCAR, ESMA75-453128700-1340, Version 3, 15.7.2025, Question 4.1"
    )


def test_bafin_rundschreiben_bait() -> None:
    out = render_citation(
        BaFinRundschreibenParts(
            number="10/2017",
            area="BA",
            short_name="BAIT",
            fassung="Fassung v. 16.8.2023",
            point="AT 7.2",
            rn=1,
        )
    )
    assert out == "BaFin-Rundschreiben 10/2017 (BA), BAIT, Fassung v. 16.8.2023, AT 7.2 Rn. 1"


def test_bafin_merkblatt_factoring() -> None:
    out = render_citation(
        BaFinMerkblattParts(name="Merkblatt Factoring", stand="Stand Januar 2014", point="unter II. 1.")
    )
    assert out == "BaFin, Merkblatt Factoring, Stand Januar 2014, unter II. 1."


def test_kwg_paragraph() -> None:
    out = render_citation(
        GermanLawParts(short_name="KWG", paragraph=1, absatz=1, satz=2, nr=9)
    )
    assert out == "§ 1 Abs. 1 Satz 2 Nr. 9 KWG"


def test_normalize_handles_variants() -> None:
    assert (
        normalize("Artikel 16  Absatz 1   Nummer 3 MiCAR")
        == "Art. 16 Abs. 1 Nr. 3 MiCAR"
    )
