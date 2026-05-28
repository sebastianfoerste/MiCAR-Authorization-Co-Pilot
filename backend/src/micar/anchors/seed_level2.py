"""Official Level 2 instruments required by the implemented MiCAR templates.

The catalogue is deliberately narrow. It includes adopted delegated and
implementing regulations that directly govern a live CASP, ART or EMT
template. Official text is fetched separately through the Publications Office
endpoint and remains unavailable for approval until curator verification.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from micar.anchors.citation import EUCitationParts, render_citation
from micar.anchors.seed_micar import SeedAnchor
from micar.models import AnchorAuthority, AnchorLevel

_OFFICIAL_CELEX_BASE = "https://publications.europa.eu/resource/celex"


@dataclass(frozen=True)
class OfficialLevel2Instrument:
    instrument_number: str
    celex: str
    short_name: str
    title: str
    publication_version: str
    applicable_from: date
    act_kind: Literal["delegated", "implementing"]
    tags: tuple[str, ...]

    @property
    def citation_canonical(self) -> str:
        return render_citation(
            EUCitationParts(
                instrument_number=self.instrument_number,
                instrument_kind="VO",
                short_name_override=self.short_name,
            )
        )

    @property
    def source_url(self) -> str:
        return f"{_OFFICIAL_CELEX_BASE}/{self.celex}"

    @property
    def binding_force_note(self) -> str:
        if self.act_kind == "delegated":
            return (
                "Level 2: Delegierte Verordnung auf Grundlage eines RTS; als in Kraft "
                "getretener Rechtsakt unmittelbar anwendbar."
            )
        return (
            "Level 2: Durchführungsverordnung auf Grundlage eines ITS; als in Kraft "
            "getretener Rechtsakt unmittelbar anwendbar."
        )

    def to_seed(self) -> SeedAnchor:
        return SeedAnchor(
            citation_canonical=self.citation_canonical,
            level=AnchorLevel.LEVEL_2,
            authority=AnchorAuthority.EU_REG,
            url=self.source_url,
            version=self.publication_version,
            effective_from=self.applicable_from,
            effective_to=None,
            title=self.title,
            body="",
            binding_force_note=self.binding_force_note,
            tags=self.tags,
        )


_INSTRUMENTS = (
    OfficialLevel2Instrument(
        instrument_number="2025/305",
        celex="32025R0305",
        short_name="MiCAR-CASP-Antrags-RTS",
        title="Informationen im Antrag auf Zulassung als Anbieter von Kryptowerte-Dienstleistungen",
        publication_version="2025-03-31",
        applicable_from=date(2025, 4, 20),
        act_kind="delegated",
        tags=("casp", "authorisation", "rts"),
    ),
    OfficialLevel2Instrument(
        instrument_number="2025/306",
        celex="32025R0306",
        short_name="MiCAR-CASP-Antrags-ITS",
        title="Standardformulare, Mustertexte und Verfahren für den CASP-Zulassungsantrag",
        publication_version="2025-03-31",
        applicable_from=date(2025, 4, 20),
        act_kind="implementing",
        tags=("casp", "authorisation", "its"),
    ),
    OfficialLevel2Instrument(
        instrument_number="2025/294",
        celex="32025R0294",
        short_name="MiCAR-CASP-Beschwerde-RTS",
        title="Anforderungen an Beschwerdeverfahren von Anbietern von Kryptowerte-Dienstleistungen",
        publication_version="2025-02-13",
        applicable_from=date(2025, 3, 5),
        act_kind="delegated",
        tags=("casp", "complaints", "rts"),
    ),
    OfficialLevel2Instrument(
        instrument_number="2025/1142",
        celex="32025R1142",
        short_name="MiCAR-CASP-Interessenkonflikt-RTS",
        title="Interessenkonflikte von Anbietern von Kryptowerte-Dienstleistungen",
        publication_version="2025-06-10",
        applicable_from=date(2025, 6, 30),
        act_kind="delegated",
        tags=("casp", "conflicts", "rts"),
    ),
    OfficialLevel2Instrument(
        instrument_number="2025/885",
        celex="32025R0885",
        short_name="MiCAR-Marktmissbrauch-RTS",
        title="Vorkehrungen, Systeme und Verfahren zur Verhinderung und Meldung von Marktmissbrauch",
        publication_version="2025-08-20",
        applicable_from=date(2025, 9, 9),
        act_kind="delegated",
        tags=("casp", "market_abuse", "rts"),
    ),
    OfficialLevel2Instrument(
        instrument_number="2025/1264",
        celex="32025R1264",
        short_name="MiCAR-Liquiditätsmanagement-RTS",
        title=(
            "Mindestinhalt der Strategien und Verfahren für das Liquiditätsmanagement "
            "bestimmter ART- und EMT-Emittenten"
        ),
        publication_version="2025-10-03",
        applicable_from=date(2025, 10, 23),
        act_kind="delegated",
        tags=("art", "emt", "liquidity", "rts"),
    ),
    OfficialLevel2Instrument(
        instrument_number="2025/1125",
        celex="32025R1125",
        short_name="MiCAR-ART-Antrags-RTS",
        title="Informationen im Antrag auf Zulassung zum Angebot vermögenswertereferenzierter Token",
        publication_version="2025-09-15",
        applicable_from=date(2025, 10, 5),
        act_kind="delegated",
        tags=("art", "authorisation", "rts"),
    ),
    OfficialLevel2Instrument(
        instrument_number="2025/1126",
        celex="32025R1126",
        short_name="MiCAR-ART-Antrags-ITS",
        title="Standardformulare, Mustertexte und Verfahren für den ART-Zulassungsantrag",
        publication_version="2025-09-15",
        applicable_from=date(2025, 10, 5),
        act_kind="implementing",
        tags=("art", "authorisation", "its"),
    ),
    OfficialLevel2Instrument(
        instrument_number="2024/2984",
        celex="32024R2984",
        short_name="MiCAR-Whitepaper-ITS",
        title="Formulare, Formate und Mustertexte für Kryptowerte-Whitepaper",
        publication_version="2024-12-03",
        applicable_from=date(2025, 12, 23),
        act_kind="implementing",
        tags=("art", "emt", "whitepaper", "its"),
    ),
)


def official_level2_instruments() -> tuple[OfficialLevel2Instrument, ...]:
    return _INSTRUMENTS


def all_level2() -> list[SeedAnchor]:
    return [instrument.to_seed() for instrument in _INSTRUMENTS]
