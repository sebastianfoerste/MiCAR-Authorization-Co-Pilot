"""Provisional pointers for ESMA, EBA and BaFin source material.

These entries provide discovery links only. They are not current-law evidence
and cannot support external synthesis until source text is fetched and reviewed.
"""
from __future__ import annotations

from datetime import date

from micar.anchors.citation import (
    BaFinMerkblattParts,
    BaFinRundschreibenParts,
    EBACitationParts,
    ESMACitationParts,
    render_citation,
)
from micar.anchors.seed_micar import SeedAnchor
from micar.models import AnchorAuthority, AnchorLevel

UNVERIFIED_SOURCE_NOTE = (
    "Ungeprüfter Quellenhinweis. Amtliche Fassung und Relevanz vor Verwendung prüfen."
)


def esma_micar_qa_anchors() -> list[SeedAnchor]:
    """ESMA Q&A on MiCAR — placeholder entries for the document headers.

    The live ingest will split this into per-question anchors. Until then we
    keep one anchor per Q&A document so templates can reference the document
    as a whole.
    """
    return [
        SeedAnchor(
            citation_canonical=render_citation(
                ESMACitationParts(
                    document_label="Q&A on MiCAR",
                    document_id="ESMA75-453128700-1340",
                    version="unverified",
                    date="laufend",
                )
            ),
            level=AnchorLevel.LEVEL_3,
            authority=AnchorAuthority.ESMA,
            url="https://www.esma.europa.eu/publications-and-data/questions-and-answers",
            version="unverified",
            effective_from=date(2024, 12, 30),
            effective_to=None,
            title="ESMA Q&A on MiCAR (document)",
            body="",
            binding_force_note=UNVERIFIED_SOURCE_NOTE,
            tags=("esma", "qa", "seed_unverified"),
        ),
    ]


def eba_micar_qa_anchors() -> list[SeedAnchor]:
    return [
        SeedAnchor(
            citation_canonical=render_citation(
                EBACitationParts(
                    document_label="Q&A on MiCAR (joint with ESMA where applicable)",
                    document_id="EBA-MiCAR-QA",
                    version="unverified",
                    date="laufend",
                )
            ),
            level=AnchorLevel.LEVEL_3,
            authority=AnchorAuthority.EBA,
            url="https://www.eba.europa.eu/single-rule-book-qa",
            version="unverified",
            effective_from=date(2024, 6, 30),
            effective_to=None,
            title="EBA Q&A on MiCAR (document)",
            body="",
            binding_force_note=UNVERIFIED_SOURCE_NOTE,
            tags=("eba", "qa", "seed_unverified"),
        ),
    ]


def bafin_anchors() -> list[SeedAnchor]:
    """BaFin Merkblätter and Rundschreiben relevant for MiCAR licensing.

    Conservative seed — covers the documents most often referenced in CASP / EMT
    intake calls. Live ingest (Phase 5) keeps versions in sync.
    """
    anchors: list[SeedAnchor] = []

    anchors.append(
        SeedAnchor(
            citation_canonical=render_citation(
                BaFinRundschreibenParts(
                    number="10/2017",
                    area="BA",
                    short_name="BAIT",
                    fassung="Fassung v. 16.8.2023",
                )
            ),
            level=AnchorLevel.LEVEL_3,
            authority=AnchorAuthority.BAFIN,
            url=(
                "https://www.bafin.de/SharedDocs/Veroeffentlichungen/DE/"
                "Rundschreiben/2017/rs_1710_ba_BAIT.html"
            ),
            version="16.8.2023",
            effective_from=date(2023, 8, 16),
            effective_to=None,
            title="BAIT: Bankaufsichtliche Anforderungen an die IT",
            body="",
            binding_force_note=UNVERIFIED_SOURCE_NOTE,
            tags=("bafin", "ict", "ba"),
        )
    )

    anchors.append(
        SeedAnchor(
            citation_canonical=render_citation(
                BaFinRundschreibenParts(
                    number="5/2023",
                    area="BA",
                    short_name="MaRisk",
                    fassung="Fassung v. 29.6.2023",
                )
            ),
            level=AnchorLevel.LEVEL_3,
            authority=AnchorAuthority.BAFIN,
            url=(
                "https://www.bafin.de/SharedDocs/Veroeffentlichungen/DE/"
                "Rundschreiben/2023/rs_0523_ba_marisk.html"
            ),
            version="29.6.2023",
            effective_from=date(2023, 6, 29),
            effective_to=None,
            title="MaRisk: Mindestanforderungen an das Risikomanagement",
            body="",
            binding_force_note=UNVERIFIED_SOURCE_NOTE,
            tags=("bafin", "risk", "ba"),
        )
    )

    anchors.append(
        SeedAnchor(
            citation_canonical=render_citation(
                BaFinMerkblattParts(
                    name="Merkblatt zum Tatbestand des Kryptoverwahrgeschäfts",
                    stand="Stand: April 2024",
                )
            ),
            level=AnchorLevel.LEVEL_3,
            authority=AnchorAuthority.BAFIN,
            url=(
                "https://www.bafin.de/SharedDocs/Veroeffentlichungen/DE/"
                "Merkblatt/BA/mb_kryptoverwahrgeschaeft.html"
            ),
            version="April-2024",
            effective_from=date(2024, 4, 1),
            effective_to=None,
            title="BaFin-Merkblatt Kryptoverwahrgeschäft",
            body="",
            binding_force_note=UNVERIFIED_SOURCE_NOTE,
            tags=("bafin", "casp", "custody"),
        )
    )

    anchors.append(
        SeedAnchor(
            citation_canonical=render_citation(
                BaFinMerkblattParts(
                    name="Merkblatt: Hinweise zur Erlaubnis nach § 32 KWG",
                    stand="Stand: Juli 2023",
                )
            ),
            level=AnchorLevel.LEVEL_3,
            authority=AnchorAuthority.BAFIN,
            url=(
                "https://www.bafin.de/SharedDocs/Veroeffentlichungen/DE/"
                "Merkblatt/BA/mb_erlaubnisantrag_inst.html"
            ),
            version="Juli-2023",
            effective_from=date(2023, 7, 1),
            effective_to=None,
            title="BaFin-Hinweise zur Erlaubnis nach § 32 KWG",
            body="",
            binding_force_note=UNVERIFIED_SOURCE_NOTE,
            tags=("bafin", "casp", "authorisation"),
        )
    )

    return anchors


def all_external() -> list[SeedAnchor]:
    return esma_micar_qa_anchors() + eba_micar_qa_anchors() + bafin_anchors()
