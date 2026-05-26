"""MiCAR Reg (EU) 2023/1114 seed corpus.

Holds structural anchor stubs (article number, canonical citation, source URL)
for every article in the substantive titles. Official article text flows in
through `micar.anchors.ingest eurlex` and is unverified until curator review.

This module is data-only. Importing it constructs the list; the ingest CLI
walks it and persists to the database.

Coverage scope:
  - Title I: scope, subject matter, definitions (Art. 1-3)
  - Title II: crypto-assets offering rules (Art. 4-15)
  - Title III: ART (Art. 16-47)
  - Title IV: EMT (Art. 48-58)
  - Title V: CASP authorisation + organisational (Art. 59-85)
  - Title VI: market abuse (Art. 86-92)
  - Selected recitals as provisional seed pointers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from micar.anchors.citation import EUCitationParts, render_citation
from micar.models import AnchorAuthority, AnchorLevel, SourceStatus


@dataclass(frozen=True)
class SeedAnchor:
    citation_canonical: str
    level: AnchorLevel
    authority: AnchorAuthority
    url: str
    version: str
    effective_from: date | None
    effective_to: date | None
    title: str = ""
    body: str = ""
    binding_force_note: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    needs_enrichment: bool = True
    source_status: str = SourceStatus.SEED_UNVERIFIED.value


MICAR_NUMBER = "2023/1114"
# MiCAR entered into force on 29 June 2023; ART/EMT provisions applied from 30
# June 2024; CASP provisions from 30 December 2024.
_ART_EMT_EFFECTIVE = date(2024, 6, 30)
_GENERAL_EFFECTIVE = date(2024, 12, 30)

# EUR-Lex pinpoint URL template. Article pinpoints use the format
#   .../?uri=CELEX:32023R1114#d1e3214-2-1
# The CELEX-only base form below is stable and lands on the consolidated text;
# the live fetcher upgrades the URL to a pinpoint anchor.
_EUR_LEX_BASE = "https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:32023R1114"


def _eu_url(article: int | None = None, recital: int | None = None) -> str:
    if article is not None:
        return f"{_EUR_LEX_BASE}#art_{article}"
    if recital is not None:
        return f"{_EUR_LEX_BASE}#rec_{recital}"
    return _EUR_LEX_BASE


def micar_articles(*, level: AnchorLevel = AnchorLevel.LEVEL_1) -> list[SeedAnchor]:
    """Return the substantive-article anchor stubs."""
    anchors: list[SeedAnchor] = []
    # Titles I + II + III + IV + V + VI — substantive provisions
    for art in range(1, 93):
        # ART (Title III) effective 30.6.2024; CASP (Title V+) effective 30.12.2024.
        if 16 <= art <= 58:
            eff = _ART_EMT_EFFECTIVE
            tags = ("art",) if art <= 47 else ("emt",)
        elif 59 <= art <= 85:
            eff = _GENERAL_EFFECTIVE
            tags = ("casp",)
        elif 86 <= art <= 92:
            eff = _GENERAL_EFFECTIVE
            tags = ("market_abuse",)
        else:
            eff = _GENERAL_EFFECTIVE
            tags = ("scope",) if art <= 15 else ()

        citation = render_citation(
            EUCitationParts(instrument_number=MICAR_NUMBER, instrument_kind="VO", article=art)
        )
        anchors.append(
            SeedAnchor(
                citation_canonical=citation,
                level=level,
                authority=AnchorAuthority.EU_REG,
                url=_eu_url(article=art),
                version="2023-06-09",  # OJ publication date
                effective_from=eff,
                effective_to=None,
                title="",
                body="",
                binding_force_note=(
                    "Level 1: direkt anwendbare Verordnung (Art. 288 Abs. 2 AEUV). "
                    "Wirksam ab dem in MiCAR Art. 149 genannten Stichtag der jeweiligen Titel."
                ),
                tags=tags,
                needs_enrichment=True,
            )
        )
    return anchors


# Provisional recital pointers. These require the same source review as articles.
_RECITALS: dict[int, str] = {
    11: "Tokens als Finanzinstrumente: Abgrenzung zu MiFID II",
    22: "Bedeutung des Krypto-Werte-Whitepapers",
    41: "ART als technologieneutrale Antwort auf Stablecoins",
    44: "EMT als regulatorische Brücke zu E-Geld",
    71: "CASP-Pflichten als Spiegel der MiFID-II-Wohlverhaltensregeln",
    72: "Vermeidung der Doppelregulierung MiFID/MiCAR",
}


def micar_recitals() -> list[SeedAnchor]:
    anchors: list[SeedAnchor] = []
    for rec, title in _RECITALS.items():
        citation = render_citation(
            EUCitationParts(instrument_number=MICAR_NUMBER, instrument_kind="VO", recital=rec)
        )
        anchors.append(
            SeedAnchor(
                citation_canonical=citation,
                level=AnchorLevel.LEVEL_1,
                authority=AnchorAuthority.EU_REG,
                url=_eu_url(recital=rec),
                version="2023-06-09",
                effective_from=_ART_EMT_EFFECTIVE,
                effective_to=None,
                title=title,
                body="",
                binding_force_note=(
                    "Erwägungsgrund: Auslegungshilfe ohne selbstständige Bindungswirkung. "
                    "Auslegungsrelevanz im Einzelfall prüfen."
                ),
                tags=("recital",),
                needs_enrichment=True,
            )
        )
    return anchors


def all_micar() -> list[SeedAnchor]:
    return micar_articles() + micar_recitals()
