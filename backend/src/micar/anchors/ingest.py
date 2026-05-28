"""Anchor ingest and official-text refresh CLI.

Two operating modes:

  uv run python -m micar.anchors.ingest seed
      Loads the hand-authored seed corpus (MiCAR articles, recitals, ESMA/EBA
      Q&A document headers, BaFin Merkblätter pointers). Idempotent —
      upserts by (citation_canonical, version).

  uv run python -m micar.anchors.ingest eurlex --regulation 2023/1114
      Fetches the official German OJ publication through the Publications
      Office CELEX endpoint and stores article text with a source fingerprint.
      Refreshed text remains `fetched_unverified` until curator approval.

  uv run python -m micar.anchors.ingest eurlex-level2
      Fetches official German text for the adopted Level 2 instruments cited
      by the live CASP, ART and EMT templates.

  uv run python -m micar.anchors.ingest eba-guidelines
      Fetches official German PDF text for the EBA and joint EBA/ESMA
      guidelines cited by live templates.

The seed mode creates unverified structural pointers without an external
network dependency. Official refresh modes perform live official-source loads.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from sqlalchemy import select

from micar.anchors.changes import record_anchor_change
from micar.anchors.seed_external import all_external, eba_micar_guideline_anchors
from micar.anchors.seed_level2 import all_level2, official_level2_instruments
from micar.anchors.seed_micar import SeedAnchor, all_micar, micar_articles
from micar.compliance.audit import write_audit
from micar.models import Anchor, SourceStatus, session_scope

OFFICIAL_MICAR_SOURCE_URL = "https://publications.europa.eu/resource/celex/32023R1114"


@dataclass(frozen=True)
class OfficialArticle:
    number: int
    title: str
    body: str
    fingerprint: str


@dataclass(frozen=True)
class OfficialDocument:
    citation_canonical: str
    body: str
    fingerprint: str
    source_url: str


def _upsert(session, seed: SeedAnchor) -> tuple[Anchor, bool]:
    existing = session.execute(
        select(Anchor).where(
            Anchor.citation_canonical == seed.citation_canonical,
            Anchor.version == seed.version,
        )
    ).scalar_one_or_none()
    if existing:
        existing.level = seed.level.value
        existing.authority = seed.authority.value
        if existing.source_status == SourceStatus.SEED_UNVERIFIED.value:
            existing.url = seed.url
        existing.effective_from = seed.effective_from
        existing.effective_to = seed.effective_to
        if seed.body:
            existing.body = existing.body or seed.body
        if seed.binding_force_note:
            existing.binding_force_note = seed.binding_force_note
        if not existing.source_status:
            existing.source_status = seed.source_status
        return existing, False
    anchor = Anchor(
        citation_canonical=seed.citation_canonical,
        level=seed.level.value,
        authority=seed.authority.value,
        url=seed.url,
        version=seed.version,
        effective_from=seed.effective_from,
        effective_to=seed.effective_to,
        body=seed.body or None,
        binding_force_note=seed.binding_force_note or None,
        source_status=seed.source_status,
    )
    session.add(anchor)
    session.flush()
    return anchor, True


def ingest_seed(seeds: Iterable[SeedAnchor]) -> dict[str, int]:
    inserted = 0
    updated = 0
    with session_scope() as session:
        for seed in seeds:
            _, created = _upsert(session, seed)
            inserted += int(created)
            updated += int(not created)
    return {"inserted": inserted, "updated": updated}


def parse_official_micar_articles(document: str) -> dict[int, OfficialArticle]:
    """Extract article-level German text from the official XHTML publication."""
    soup = BeautifulSoup(document, "xml")
    articles: dict[int, OfficialArticle] = {}
    for node in soup.select("div.eli-subdivision[id^='art_']"):
        source_id = node.get("id", "")
        try:
            number = int(source_id.removeprefix("art_"))
        except ValueError:
            continue
        title_node = node.select_one("p.oj-sti-art")
        title = title_node.get_text(" ", strip=True) if title_node else ""
        body = "\n".join(node.stripped_strings)
        fingerprint = hashlib.sha256(body.encode("utf-8")).hexdigest()
        articles[number] = OfficialArticle(number=number, title=title, body=body, fingerprint=fingerprint)
    return articles


def fetch_official_micar_articles() -> dict[int, OfficialArticle]:
    response = httpx.get(
        OFFICIAL_MICAR_SOURCE_URL,
        headers={"Accept": "application/xhtml+xml", "Accept-Language": "deu"},
        follow_redirects=True,
        timeout=30.0,
    )
    response.raise_for_status()
    articles = parse_official_micar_articles(response.text)
    if not all(article_number in articles for article_number in range(1, 93)):
        raise ValueError("official MiCAR response did not contain articles 1 to 92")
    return articles


def parse_official_level2_document(
    document: str, *, citation_canonical: str, instrument_number: str, source_url: str
) -> OfficialDocument:
    """Extract full German text for one adopted Level 2 instrument."""
    soup = BeautifulSoup(document, "xml")
    body = "\n".join(soup.stripped_strings)
    if len(body) < 500 or instrument_number not in body or "VERORDNUNG" not in body:
        raise ValueError(f"official source did not contain expected instrument {instrument_number}")
    return OfficialDocument(
        citation_canonical=citation_canonical,
        body=body,
        fingerprint=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        source_url=source_url,
    )


def fetch_official_level2_documents() -> dict[str, OfficialDocument]:
    documents: dict[str, OfficialDocument] = {}
    for instrument in official_level2_instruments():
        response = httpx.get(
            instrument.source_url,
            headers={"Accept": "application/xhtml+xml", "Accept-Language": "deu"},
            follow_redirects=True,
            timeout=30.0,
        )
        response.raise_for_status()
        document = parse_official_level2_document(
            response.text,
            citation_canonical=instrument.citation_canonical,
            instrument_number=instrument.instrument_number,
            source_url=instrument.source_url,
        )
        documents[instrument.citation_canonical] = document
    return documents


def _guideline_expected_terms(seed: SeedAnchor) -> tuple[str, ...]:
    if seed.authority.value == "eba_esma":
        return ("EBA/GL/2024/09", "ESMA75-453128700-10")
    return (seed.version,)


def parse_official_guideline_pdf(
    document: bytes, *, citation_canonical: str, expected_terms: tuple[str, ...], source_url: str
) -> OfficialDocument:
    """Extract full text from an official EBA-hosted guideline PDF."""
    if not document.startswith(b"%PDF"):
        raise ValueError("official guideline response was not a PDF")
    reader = PdfReader(BytesIO(document))
    pages: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        cleaned = "\n".join(line.strip() for line in page_text.splitlines() if line.strip())
        if cleaned:
            pages.append(cleaned)
    body = "\n\n".join(pages)
    missing = [term for term in expected_terms if term not in body]
    if len(body) < 500 or missing:
        raise ValueError(
            f"official guideline source did not contain expected terms for {citation_canonical}: {missing}"
        )
    return OfficialDocument(
        citation_canonical=citation_canonical,
        body=body,
        fingerprint=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        source_url=source_url,
    )


def fetch_official_level3_guideline_documents() -> dict[str, OfficialDocument]:
    documents: dict[str, OfficialDocument] = {}
    for seed in eba_micar_guideline_anchors():
        response = httpx.get(
            seed.url,
            headers={"Accept": "application/pdf", "Accept-Language": "deu"},
            follow_redirects=True,
            timeout=60.0,
        )
        response.raise_for_status()
        documents[seed.citation_canonical] = parse_official_guideline_pdf(
            response.content,
            citation_canonical=seed.citation_canonical,
            expected_terms=_guideline_expected_terms(seed),
            source_url=seed.url,
        )
    return documents


def ingest_official_micar_articles(
    articles: dict[int, OfficialArticle] | None = None,
) -> dict[str, int]:
    official = articles or fetch_official_micar_articles()
    inserted = 0
    refreshed = 0
    preserved_verified = 0
    changes_detected = 0
    now = datetime.now(UTC)
    with session_scope() as session:
        for number, seed in enumerate(micar_articles(), start=1):
            row, created = _upsert(session, seed)
            article = official[number]
            prior_fingerprint = row.source_fingerprint
            was_verified_unchanged = (
                row.source_status == SourceStatus.VERIFIED.value and prior_fingerprint == article.fingerprint
            )
            row.body = article.body
            row.url = f"{OFFICIAL_MICAR_SOURCE_URL}#art_{number}"
            row.source_fingerprint = article.fingerprint
            row.source_retrieved_at = now
            if was_verified_unchanged:
                preserved_verified += 1
            else:
                row.source_status = SourceStatus.FETCHED_UNVERIFIED.value
                row.reviewed_at = None
                row.reviewed_by = None
            if prior_fingerprint and prior_fingerprint != article.fingerprint:
                record_anchor_change(
                    session,
                    anchor=row,
                    prior_fingerprint=prior_fingerprint,
                    source_url=row.url,
                    summary="Official MiCAR article fingerprint changed; curator verification required.",
                )
                changes_detected += 1
            inserted += int(created)
            refreshed += 1
        write_audit(
            session,
            kind="anchor.official.refresh",
            payload={
                "source": "official_micar",
                "inserted": inserted,
                "refreshed": refreshed,
                "preserved_verified": preserved_verified,
                "changes_detected": changes_detected,
            },
        )
    return {
        "inserted": inserted,
        "refreshed": refreshed,
        "preserved_verified": preserved_verified,
        "changes_detected": changes_detected,
    }


def ingest_official_level2_documents(
    documents: dict[str, OfficialDocument] | None = None,
) -> dict[str, int]:
    official = documents or fetch_official_level2_documents()
    inserted = 0
    refreshed = 0
    preserved_verified = 0
    changes_detected = 0
    now = datetime.now(UTC)
    with session_scope() as session:
        for seed in all_level2():
            row, created = _upsert(session, seed)
            document = official[seed.citation_canonical]
            prior_fingerprint = row.source_fingerprint
            was_verified_unchanged = (
                row.source_status == SourceStatus.VERIFIED.value and prior_fingerprint == document.fingerprint
            )
            row.body = document.body
            row.url = document.source_url
            row.source_fingerprint = document.fingerprint
            row.source_retrieved_at = now
            if was_verified_unchanged:
                preserved_verified += 1
            else:
                row.source_status = SourceStatus.FETCHED_UNVERIFIED.value
                row.reviewed_at = None
                row.reviewed_by = None
            if prior_fingerprint and prior_fingerprint != document.fingerprint:
                record_anchor_change(
                    session,
                    anchor=row,
                    prior_fingerprint=prior_fingerprint,
                    source_url=row.url,
                    summary="Official Level 2 instrument fingerprint changed; curator verification required.",
                )
                changes_detected += 1
            inserted += int(created)
            refreshed += 1
        write_audit(
            session,
            kind="anchor.official.refresh",
            payload={
                "source": "official_micar_level2",
                "inserted": inserted,
                "refreshed": refreshed,
                "preserved_verified": preserved_verified,
                "changes_detected": changes_detected,
            },
        )
    return {
        "inserted": inserted,
        "refreshed": refreshed,
        "preserved_verified": preserved_verified,
        "changes_detected": changes_detected,
    }


def ingest_official_level3_guideline_documents(
    documents: dict[str, OfficialDocument] | None = None,
) -> dict[str, int]:
    official = documents or fetch_official_level3_guideline_documents()
    inserted = 0
    refreshed = 0
    preserved_verified = 0
    changes_detected = 0
    now = datetime.now(UTC)
    with session_scope() as session:
        for seed in eba_micar_guideline_anchors():
            row, created = _upsert(session, seed)
            document = official[seed.citation_canonical]
            prior_fingerprint = row.source_fingerprint
            was_verified_unchanged = (
                row.source_status == SourceStatus.VERIFIED.value and prior_fingerprint == document.fingerprint
            )
            row.body = document.body
            row.url = document.source_url
            row.source_fingerprint = document.fingerprint
            row.source_retrieved_at = now
            if was_verified_unchanged:
                preserved_verified += 1
            else:
                row.source_status = SourceStatus.FETCHED_UNVERIFIED.value
                row.reviewed_at = None
                row.reviewed_by = None
            if prior_fingerprint and prior_fingerprint != document.fingerprint:
                record_anchor_change(
                    session,
                    anchor=row,
                    prior_fingerprint=prior_fingerprint,
                    source_url=row.url,
                    summary="Official Level 3 guideline fingerprint changed; curator verification required.",
                )
                changes_detected += 1
            inserted += int(created)
            refreshed += 1
        write_audit(
            session,
            kind="anchor.official.refresh",
            payload={
                "source": "official_level3_guidelines",
                "inserted": inserted,
                "refreshed": refreshed,
                "preserved_verified": preserved_verified,
                "changes_detected": changes_detected,
            },
        )
    return {
        "inserted": inserted,
        "refreshed": refreshed,
        "preserved_verified": preserved_verified,
        "changes_detected": changes_detected,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="micar.anchors.ingest")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed", help="Load hand-authored seed corpus")
    eurlex = sub.add_parser("eurlex", help="Refresh MiCAR article text from official CELEX source")
    eurlex.add_argument("--regulation", required=True)
    sub.add_parser("eurlex-level2", help="Refresh official Level 2 text cited by templates")
    sub.add_parser("eba-guidelines", help="Refresh official EBA and joint EBA/ESMA guideline PDFs")

    args = parser.parse_args(argv)
    if args.cmd == "seed":
        result = ingest_seed(all_micar() + all_level2() + all_external())
        print(f"seed ingest: inserted={result['inserted']} updated={result['updated']}")
        return 0
    if args.cmd == "eurlex":
        if args.regulation != "2023/1114":
            parser.error("only MiCAR Regulation (EU) 2023/1114 is supported")
        result = ingest_official_micar_articles()
        print(
            "official ingest: "
            f"inserted={result['inserted']} refreshed={result['refreshed']} "
            f"preserved_verified={result['preserved_verified']} "
            f"changes_detected={result['changes_detected']}"
        )
        return 0
    if args.cmd == "eurlex-level2":
        result = ingest_official_level2_documents()
        print(
            "official Level 2 ingest: "
            f"inserted={result['inserted']} refreshed={result['refreshed']} "
            f"preserved_verified={result['preserved_verified']} "
            f"changes_detected={result['changes_detected']}"
        )
        return 0
    if args.cmd == "eba-guidelines":
        result = ingest_official_level3_guideline_documents()
        print(
            "official Level 3 guideline ingest: "
            f"inserted={result['inserted']} refreshed={result['refreshed']} "
            f"preserved_verified={result['preserved_verified']} "
            f"changes_detected={result['changes_detected']}"
        )
        return 0
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
