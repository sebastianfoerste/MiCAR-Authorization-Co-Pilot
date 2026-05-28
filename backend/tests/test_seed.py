"""Verify the seed corpus is well-formed without requiring a live DB."""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager

from micar.anchors import ingest
from micar.anchors.ingest import (
    OfficialArticle,
    OfficialDocument,
    parse_official_guideline_pdf,
    parse_official_level2_document,
    parse_official_micar_articles,
)
from micar.anchors.seed_external import all_external, eba_micar_guideline_anchors
from micar.anchors.seed_level2 import all_level2
from micar.anchors.seed_micar import all_micar
from micar.models import Anchor, SourceStatus


def test_micar_seed_coverage() -> None:
    items = all_micar()
    # 92 substantive articles + 6 recitals
    assert len(items) == 98
    citations = {i.citation_canonical for i in items}
    assert "Art. 16 VO (EU) 2023/1114 (MiCAR)" in citations
    assert "Art. 68 VO (EU) 2023/1114 (MiCAR)" in citations
    assert "Erwägungsgrund 11 MiCAR" in citations


def test_micar_seed_no_duplicate_citations() -> None:
    items = all_micar()
    counts = Counter(i.citation_canonical for i in items)
    dupes = {c: n for c, n in counts.items() if n > 1}
    assert not dupes, f"duplicate citations: {dupes}"


def test_micar_seed_articles_have_urls() -> None:
    items = all_micar()
    for it in items:
        assert it.url and it.url.startswith("https://eur-lex.europa.eu/")


def test_external_seed_present() -> None:
    items = all_external()
    titles = {i.title for i in items}
    assert "BAIT: Bankaufsichtliche Anforderungen an die IT" in titles
    assert "BaFin-Merkblatt Kryptoverwahrgeschäft" in titles
    assert "EBA-Leitlinien über Sanierungspläne nach MiCAR" in titles
    assert "Gemeinsame EBA/ESMA-Leitlinien zur Eignung nach MiCAR" in titles


def test_level2_seed_contains_official_instruments_used_by_templates() -> None:
    items = all_level2()
    citations = {item.citation_canonical for item in items}

    assert len(items) == 8
    assert "VO (EU) 2025/305 (MiCAR-CASP-Antrags-RTS)" in citations
    assert "VO (EU) 2025/885 (MiCAR-Marktmissbrauch-RTS)" in citations
    assert "VO (EU) 2025/1125 (MiCAR-ART-Antrags-RTS)" in citations
    assert "VO (EU) 2024/2984 (MiCAR-Whitepaper-ITS)" in citations
    assert all(item.level.value == "level_2" for item in items)


def test_level2_seed_uses_applicability_dates() -> None:
    items = {item.citation_canonical: item for item in all_level2()}

    assert str(items["VO (EU) 2025/305 (MiCAR-CASP-Antrags-RTS)"].effective_from) == "2025-04-20"
    assert str(items["VO (EU) 2025/885 (MiCAR-Marktmissbrauch-RTS)"].effective_from) == "2025-09-09"
    assert str(items["VO (EU) 2024/2984 (MiCAR-Whitepaper-ITS)"].effective_from) == "2025-12-23"
    assert "Delegierte Verordnung" in items["VO (EU) 2025/305 (MiCAR-CASP-Antrags-RTS)"].binding_force_note
    assert "Durchführungsverordnung" in items["VO (EU) 2024/2984 (MiCAR-Whitepaper-ITS)"].binding_force_note


def test_seed_anchors_carry_effective_dates() -> None:
    # ART/EMT titles apply from 2024-06-30; the general date is 2024-12-30.
    items = all_micar()
    art4 = next(i for i in items if i.citation_canonical == "Art. 4 VO (EU) 2023/1114 (MiCAR)")
    art16 = next(i for i in items if i.citation_canonical == "Art. 16 VO (EU) 2023/1114 (MiCAR)")
    art60 = next(i for i in items if i.citation_canonical == "Art. 60 VO (EU) 2023/1114 (MiCAR)")
    assert str(art4.effective_from) == "2024-12-30"
    assert str(art16.effective_from) == "2024-06-30"
    assert str(art60.effective_from) == "2024-12-30"


def test_official_article_parser_extracts_title_body_and_fingerprint() -> None:
    document = """
    <html><body>
      <div class="eli-subdivision" id="art_54">
        <p class="oj-ti-art">Artikel 54</p>
        <div class="eli-title"><p class="oj-sti-art">Anlage von Geldbeträgen</p></div>
        <p class="oj-normal">(1) Offizieller Wortlaut.</p>
      </div>
    </body></html>
    """
    articles = parse_official_micar_articles(document)

    assert articles[54].title == "Anlage von Geldbeträgen"
    assert "Offizieller Wortlaut" in articles[54].body
    assert len(articles[54].fingerprint) == 64


def test_official_level2_parser_validates_document_and_fingerprints() -> None:
    document = (
        "<html><body><p>DELEGIERTE VERORDNUNG (EU) 2025/305 "
        + "Offizieller Wortlaut. " * 35
        + "</p></body></html>"
    )

    result = parse_official_level2_document(
        document,
        citation_canonical="VO (EU) 2025/305 (MiCAR-CASP-Antrags-RTS)",
        instrument_number="2025/305",
        source_url="https://publications.europa.eu/resource/celex/32025R0305",
    )

    assert result.citation_canonical == "VO (EU) 2025/305 (MiCAR-CASP-Antrags-RTS)"
    assert "Offizieller Wortlaut" in result.body
    assert len(result.fingerprint) == 64


def test_official_guideline_pdf_parser_validates_terms_and_fingerprints(monkeypatch) -> None:
    citation = "EBA, Leitlinien über Sanierungspläne nach MiCAR, EBA/GL/2024/07, final, 13.6.2024"

    class FakePage:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class FakeReader:
        def __init__(self, _stream) -> None:
            self.pages = [FakePage("EBA/GL/2024/07 " + "Leitlinien nach MiCAR. " * 35)]

    monkeypatch.setattr(ingest, "PdfReader", FakeReader)

    result = parse_official_guideline_pdf(
        b"%PDF fixture",
        citation_canonical=citation,
        expected_terms=("EBA/GL/2024/07",),
        source_url="https://www.eba.europa.eu/test.pdf",
    )

    assert result.citation_canonical.startswith("EBA, Leitlinien")
    assert "EBA/GL/2024/07" in result.body
    assert len(result.fingerprint) == 64


def test_official_refresh_queues_a_changed_stored_fingerprint(monkeypatch) -> None:
    row = Anchor(
        id=68,
        citation_canonical="Art. 68 VO (EU) 2023/1114 (MiCAR)",
        level="level_1",
        authority="eu_regulation",
        source_status=SourceStatus.VERIFIED.value,
        source_fingerprint="old",
    )
    recorded: list[dict[str, object]] = []
    audit_payloads: list[dict[str, object] | None] = []

    @contextmanager
    def fake_scope():
        yield object()

    monkeypatch.setattr(ingest, "session_scope", fake_scope)
    monkeypatch.setattr(ingest, "micar_articles", lambda: [object()])
    monkeypatch.setattr(ingest, "_upsert", lambda _session, _seed: (row, False))
    monkeypatch.setattr(
        ingest,
        "record_anchor_change",
        lambda _session, **kwargs: recorded.append(kwargs),
    )
    monkeypatch.setattr(
        ingest,
        "write_audit",
        lambda _session, **kwargs: audit_payloads.append(kwargs.get("payload")),
    )

    result = ingest.ingest_official_micar_articles(
        {1: OfficialArticle(number=1, title="Artikel 68", body="changed", fingerprint="new")}
    )

    assert result["changes_detected"] == 1
    assert row.source_status == SourceStatus.FETCHED_UNVERIFIED.value
    assert recorded[0]["prior_fingerprint"] == "old"
    assert audit_payloads[0] == {
        "source": "official_micar",
        "inserted": 0,
        "refreshed": 1,
        "preserved_verified": 0,
        "changes_detected": 1,
    }


def test_level2_refresh_queues_a_changed_stored_fingerprint(monkeypatch) -> None:
    seed = all_level2()[0]
    row = Anchor(
        id=101,
        citation_canonical=seed.citation_canonical,
        level="level_2",
        authority="eu_regulation",
        source_status=SourceStatus.VERIFIED.value,
        source_fingerprint="old",
    )
    recorded: list[dict[str, object]] = []
    audit_payloads: list[dict[str, object] | None] = []

    @contextmanager
    def fake_scope():
        yield object()

    monkeypatch.setattr(ingest, "session_scope", fake_scope)
    monkeypatch.setattr(ingest, "all_level2", lambda: [seed])
    monkeypatch.setattr(ingest, "_upsert", lambda _session, _seed: (row, False))
    monkeypatch.setattr(
        ingest,
        "record_anchor_change",
        lambda _session, **kwargs: recorded.append(kwargs),
    )
    monkeypatch.setattr(
        ingest,
        "write_audit",
        lambda _session, **kwargs: audit_payloads.append(kwargs.get("payload")),
    )

    result = ingest.ingest_official_level2_documents(
        {
            seed.citation_canonical: OfficialDocument(
                citation_canonical=seed.citation_canonical,
                body="changed",
                fingerprint="new",
                source_url=seed.url,
            )
        }
    )

    assert result["changes_detected"] == 1
    assert row.source_status == SourceStatus.FETCHED_UNVERIFIED.value
    assert recorded[0]["prior_fingerprint"] == "old"
    assert audit_payloads[0] == {
        "source": "official_micar_level2",
        "inserted": 0,
        "refreshed": 1,
        "preserved_verified": 0,
        "changes_detected": 1,
    }


def test_level3_guideline_refresh_queues_a_changed_stored_fingerprint(monkeypatch) -> None:
    seed = eba_micar_guideline_anchors()[0]
    row = Anchor(
        id=201,
        citation_canonical=seed.citation_canonical,
        level="level_3",
        authority="eba",
        source_status=SourceStatus.VERIFIED.value,
        source_fingerprint="old",
    )
    recorded: list[dict[str, object]] = []
    audit_payloads: list[dict[str, object] | None] = []

    @contextmanager
    def fake_scope():
        yield object()

    monkeypatch.setattr(ingest, "session_scope", fake_scope)
    monkeypatch.setattr(ingest, "eba_micar_guideline_anchors", lambda: [seed])
    monkeypatch.setattr(ingest, "_upsert", lambda _session, _seed: (row, False))
    monkeypatch.setattr(
        ingest,
        "record_anchor_change",
        lambda _session, **kwargs: recorded.append(kwargs),
    )
    monkeypatch.setattr(
        ingest,
        "write_audit",
        lambda _session, **kwargs: audit_payloads.append(kwargs.get("payload")),
    )

    result = ingest.ingest_official_level3_guideline_documents(
        {
            seed.citation_canonical: OfficialDocument(
                citation_canonical=seed.citation_canonical,
                body="changed guideline",
                fingerprint="new",
                source_url=seed.url,
            )
        }
    )

    assert result["changes_detected"] == 1
    assert row.source_status == SourceStatus.FETCHED_UNVERIFIED.value
    assert recorded[0]["prior_fingerprint"] == "old"
    assert audit_payloads[0] == {
        "source": "official_level3_guidelines",
        "inserted": 0,
        "refreshed": 1,
        "preserved_verified": 0,
        "changes_detected": 1,
    }
