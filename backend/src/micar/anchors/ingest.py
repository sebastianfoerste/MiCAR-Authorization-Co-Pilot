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

The seed mode creates unverified structural pointers without an external
network dependency. The eurlex mode performs the live official MiCAR refresh.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

from micar.anchors.seed_external import all_external
from micar.anchors.seed_micar import SeedAnchor, all_micar, micar_articles
from micar.models import Anchor, SourceStatus, session_scope

OFFICIAL_MICAR_SOURCE_URL = "https://publications.europa.eu/resource/celex/32023R1114"


@dataclass(frozen=True)
class OfficialArticle:
    number: int
    title: str
    body: str
    fingerprint: str


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
        articles[number] = OfficialArticle(
            number=number, title=title, body=body, fingerprint=fingerprint
        )
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


def ingest_official_micar_articles(
    articles: dict[int, OfficialArticle] | None = None,
) -> dict[str, int]:
    official = articles or fetch_official_micar_articles()
    inserted = 0
    refreshed = 0
    preserved_verified = 0
    now = datetime.now(UTC)
    with session_scope() as session:
        for number, seed in enumerate(micar_articles(), start=1):
            row, created = _upsert(session, seed)
            article = official[number]
            was_verified_unchanged = (
                row.source_status == SourceStatus.VERIFIED.value
                and row.source_fingerprint == article.fingerprint
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
            inserted += int(created)
            refreshed += 1
    return {
        "inserted": inserted,
        "refreshed": refreshed,
        "preserved_verified": preserved_verified,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="micar.anchors.ingest")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed", help="Load hand-authored seed corpus")
    eurlex = sub.add_parser("eurlex", help="Refresh MiCAR article text from official CELEX source")
    eurlex.add_argument("--regulation", required=True)

    args = parser.parse_args(argv)
    if args.cmd == "seed":
        result = ingest_seed(all_micar() + all_external())
        print(
            f"seed ingest: inserted={result['inserted']} updated={result['updated']}"
        )
        return 0
    if args.cmd == "eurlex":
        if args.regulation != "2023/1114":
            parser.error("only MiCAR Regulation (EU) 2023/1114 is supported")
        result = ingest_official_micar_articles()
        print(
            "official ingest: "
            f"inserted={result['inserted']} refreshed={result['refreshed']} "
            f"preserved_verified={result['preserved_verified']}"
        )
        return 0
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
