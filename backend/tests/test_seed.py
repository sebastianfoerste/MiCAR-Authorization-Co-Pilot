"""Verify the seed corpus is well-formed without requiring a live DB."""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager

from micar.anchors import ingest
from micar.anchors.ingest import OfficialArticle, parse_official_micar_articles
from micar.anchors.seed_external import all_external
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
