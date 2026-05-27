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
    JointEBAESMACitationParts,
    binding_force_note,
    render_citation,
)
from micar.anchors.seed_micar import SeedAnchor
from micar.models import AnchorAuthority, AnchorLevel

UNVERIFIED_SOURCE_NOTE = "Ungeprüfter Quellenhinweis. Amtliche Fassung und Relevanz vor Verwendung prüfen."


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


def eba_micar_guideline_anchors() -> list[SeedAnchor]:
    """Applicable MiCAR guidelines directly required by authored documents."""
    return [
        SeedAnchor(
            citation_canonical=render_citation(
                EBACitationParts(
                    document_label="Leitlinien interne Governance für ART nach MiCAR",
                    document_id="EBA/GL/2024/06",
                    version="final",
                    date="6.6.2024",
                )
            ),
            level=AnchorLevel.LEVEL_3,
            authority=AnchorAuthority.EBA,
            url=(
                "https://www.eba.europa.eu/sites/default/files/2024-09/"
                "611ef3d4-4d67-467f-bf0d-4c2b1dd0ef5e/"
                "GL%20internal%20governance%20of%20issuers%20of%20ARTs"
                "%20%28EBA%20GL%202024%2006%29_DE_COR.pdf"
            ),
            version="EBA/GL/2024/06",
            effective_from=date(2024, 12, 20),
            effective_to=None,
            title="EBA-Leitlinien interne Governance für ART",
            body="",
            binding_force_note=binding_force_note(AnchorLevel.LEVEL_3, AnchorAuthority.EBA),
            tags=("eba", "art", "governance"),
        ),
        SeedAnchor(
            citation_canonical=render_citation(
                EBACitationParts(
                    document_label="Leitlinien über Sanierungspläne nach MiCAR",
                    document_id="EBA/GL/2024/07",
                    version="final",
                    date="13.6.2024",
                )
            ),
            level=AnchorLevel.LEVEL_3,
            authority=AnchorAuthority.EBA,
            url=(
                "https://www.eba.europa.eu/sites/default/files/2024-09/"
                "a4619671-df54-42ff-a6d8-2819f51ebe83/"
                "GL%20recovery%20plans%20%28EBA%20GL%202024%2007%29_DE_COR.pdf"
            ),
            version="EBA/GL/2024/07",
            effective_from=date(2024, 11, 13),
            effective_to=None,
            title="EBA-Leitlinien über Sanierungspläne nach MiCAR",
            body="",
            binding_force_note=binding_force_note(AnchorLevel.LEVEL_3, AnchorAuthority.EBA),
            tags=("eba", "art", "emt", "recovery"),
        ),
        SeedAnchor(
            citation_canonical=render_citation(
                EBACitationParts(
                    document_label="Leitlinien über Rücktauschpläne nach MiCAR",
                    document_id="EBA/GL/2024/13",
                    version="final",
                    date="9.10.2024",
                )
            ),
            level=AnchorLevel.LEVEL_3,
            authority=AnchorAuthority.EBA,
            url=(
                "https://www.eba.europa.eu/sites/default/files/2024-12/"
                "f8fda168-4d97-4549-9cfe-46d1d1a27636/"
                "GL%20on%20redemption%20plans%20under%20MiCAR"
                "%20%28EBA%20GL%202024%2013%29_DE_COR.pdf"
            ),
            version="EBA/GL/2024/13",
            effective_from=date(2025, 2, 10),
            effective_to=None,
            title="EBA-Leitlinien über Rücktauschpläne nach MiCAR",
            body="",
            binding_force_note=binding_force_note(AnchorLevel.LEVEL_3, AnchorAuthority.EBA),
            tags=("eba", "art", "emt", "redemption"),
        ),
        SeedAnchor(
            citation_canonical=render_citation(
                JointEBAESMACitationParts(
                    document_label="Leitlinien zur Eignung des Leitungsorgans nach MiCAR",
                    eba_document_id="EBA/GL/2024/09",
                    esma_document_id="ESMA75-453128700-10",
                    version="final",
                    date="4.12.2024",
                )
            ),
            level=AnchorLevel.LEVEL_3,
            authority=AnchorAuthority.EBA_ESMA,
            url=(
                "https://www.eba.europa.eu/sites/default/files/2025-04/"
                "2a0668ab-5d70-495a-a723-f6568fe8c830/"
                "Joint%20GL%20suitability%20members%20management%20body%20and%20QH_DE.pdf"
            ),
            version="EBA/GL/2024/09-ESMA75-453128700-10",
            effective_from=date(2025, 2, 4),
            effective_to=None,
            title="Gemeinsame EBA/ESMA-Leitlinien zur Eignung nach MiCAR",
            body="",
            binding_force_note=binding_force_note(AnchorLevel.LEVEL_3, AnchorAuthority.EBA_ESMA),
            tags=("eba", "esma", "art", "casp", "suitability"),
        ),
    ]


def bafin_anchors() -> list[SeedAnchor]:
    """BaFin Merkblätter and Rundschreiben relevant for MiCAR licensing.

    Conservative seed covering documents potentially relevant to CASP or EMT
    intake. Public source text must be loaded and verified before use.
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
    return esma_micar_qa_anchors() + eba_micar_qa_anchors() + eba_micar_guideline_anchors() + bafin_anchors()
