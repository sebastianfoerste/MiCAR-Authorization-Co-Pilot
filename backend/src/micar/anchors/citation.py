"""Canonical citation rendering for MiCAR drafting templates.

Rules:
  * Include Absatz / Satz / Nr. whenever the norm structure allows.
  * Include Randnummer (Rn.) for judicial decisions.
  * Distinguish Level 1 (Regulation / Directive), Level 2 (RTS / ITS / delegated
    acts), Level 3 (ESMA / EBA / BaFin guidelines, circulars) wherever the level
    affects binding force.

The functions here are pure (no DB access). The Anchor row stores the rendered
string in `citation_canonical` so SQL searches stay simple. Re-rendering on a
fresh ingest is idempotent.
"""

from __future__ import annotations

from dataclasses import dataclass

from micar.models import AnchorAuthority, AnchorLevel

# Short-name registry. Keep in one place so ingest scripts agree on the form.
SHORT_NAMES: dict[str, str] = {
    "2023/1114": "MiCAR",
    "2022/2554": "DORA",
    "2022/2065": "DSA",
    "2014/65": "MiFID II",
    "600/2014": "MiFIR",
    "2015/2366": "PSD2",
    "2009/110": "EMD2",
    "2024/1689": "KI-VO",  # AI Act
    "2024/1624": "AMLR",
}


@dataclass(frozen=True)
class EUCitationParts:
    """Pinpoint citation parts for an EU Regulation or Directive article."""

    instrument_number: str  # e.g. "2023/1114"
    instrument_kind: str  # "VO" (Verordnung) or "RL" (Richtlinie)
    article: int | None = None
    absatz: int | None = None
    satz: int | None = None
    nr: int | None = None
    lit: str | None = None  # "a", "b", "c", ...
    recital: int | None = None  # use this instead of article when citing an Erwägungsgrund
    short_name_override: str | None = None

    def render(self) -> str:
        short = self.short_name_override or SHORT_NAMES.get(self.instrument_number, "")
        suffix_paren = f" ({short})" if short else ""
        instrument = f"{self.instrument_kind} (EU) {self.instrument_number}{suffix_paren}"

        if self.recital is not None:
            short_for_recital = short or f"VO (EU) {self.instrument_number}"
            return f"Erwägungsgrund {self.recital} {short_for_recital}"

        if self.article is None:
            return instrument

        parts = [f"Art. {self.article}"]
        if self.absatz is not None:
            parts.append(f"Abs. {self.absatz}")
        if self.satz is not None:
            parts.append(f"Satz {self.satz}")
        if self.nr is not None:
            parts.append(f"Nr. {self.nr}")
        if self.lit is not None:
            parts.append(f"lit. {self.lit}")
        return f"{' '.join(parts)} {instrument}"


@dataclass(frozen=True)
class ESMACitationParts:
    """ESMA Q&A or Guidelines pinpoint."""

    document_label: str  # e.g. "Q&A on MiCAR"
    document_id: str  # e.g. "ESMA75-453128700-1340"
    version: str | int  # e.g. "Version 3" or 3
    date: str  # e.g. "15.7.2025" or "Q2 2026"
    question: str | None = None  # e.g. "Question 4.1"
    section: str | None = None  # for guidelines

    def render(self) -> str:
        version_str = f"Version {self.version}" if isinstance(self.version, int) else self.version
        head = f"ESMA, {self.document_label}, {self.document_id}, {version_str}, {self.date}"
        if self.question:
            return f"{head}, {self.question}"
        if self.section:
            return f"{head}, {self.section}"
        return head


@dataclass(frozen=True)
class EBACitationParts:
    """EBA Q&A or Guidelines pinpoint."""

    document_label: str
    document_id: str
    version: str | int
    date: str
    question: str | None = None
    section: str | None = None

    def render(self) -> str:
        version_str = f"Version {self.version}" if isinstance(self.version, int) else self.version
        head = f"EBA, {self.document_label}, {self.document_id}, {version_str}, {self.date}"
        if self.question:
            return f"{head}, {self.question}"
        if self.section:
            return f"{head}, {self.section}"
        return head


@dataclass(frozen=True)
class JointEBAESMACitationParts:
    """Joint EBA and ESMA guideline pinpoint."""

    document_label: str
    eba_document_id: str
    esma_document_id: str
    version: str | int
    date: str
    section: str | None = None

    def render(self) -> str:
        version_str = f"Version {self.version}" if isinstance(self.version, int) else self.version
        head = (
            f"EBA/ESMA, {self.document_label}, {self.eba_document_id}; "
            f"{self.esma_document_id}, {version_str}, {self.date}"
        )
        if self.section:
            return f"{head}, {self.section}"
        return head


@dataclass(frozen=True)
class BaFinRundschreibenParts:
    """BaFin Rundschreiben (e.g. BAIT, MaRisk, KAIT)."""

    number: str  # e.g. "10/2017"
    area: str  # e.g. "BA" (Bankenaufsicht), "VA", "WA"
    short_name: str | None = None  # e.g. "BAIT"
    fassung: str | None = None  # e.g. "Fassung v. 16.8.2023"
    point: str | None = None  # e.g. "AT 7.2"
    rn: int | None = None  # Randnummer

    def render(self) -> str:
        head = f"BaFin-Rundschreiben {self.number} ({self.area})"
        if self.short_name:
            head = f"{head}, {self.short_name}"
        if self.fassung:
            head = f"{head}, {self.fassung}"
        if self.point:
            head = f"{head}, {self.point}"
        if self.rn is not None:
            head = f"{head} Rn. {self.rn}"
        return head


@dataclass(frozen=True)
class BaFinMerkblattParts:
    """BaFin Merkblatt (administrative guidance, Level 3)."""

    name: str  # e.g. "Merkblatt Factoring"
    stand: str  # e.g. "Stand Januar 2014" or "Stand: April 2026"
    point: str | None = None  # e.g. "unter II. 1." or "Ziff. 3.2"

    def render(self) -> str:
        head = f"BaFin, {self.name}, {self.stand}"
        if self.point:
            head = f"{head}, {self.point}"
        return head


@dataclass(frozen=True)
class GermanLawParts:
    """German national-law citation (KWG, ZAG, GwG, KAGB, etc.)."""

    short_name: str  # "KWG", "ZAG", "GwG", "KAGB"
    paragraph: int
    absatz: int | None = None
    satz: int | None = None
    nr: int | None = None
    lit: str | None = None

    def render(self) -> str:
        parts = [f"§ {self.paragraph}"]
        if self.absatz is not None:
            parts.append(f"Abs. {self.absatz}")
        if self.satz is not None:
            parts.append(f"Satz {self.satz}")
        if self.nr is not None:
            parts.append(f"Nr. {self.nr}")
        if self.lit is not None:
            parts.append(f"lit. {self.lit}")
        return f"{' '.join(parts)} {self.short_name}"


CitationParts = (
    EUCitationParts
    | ESMACitationParts
    | EBACitationParts
    | JointEBAESMACitationParts
    | BaFinRundschreibenParts
    | BaFinMerkblattParts
    | GermanLawParts
)


def render_citation(parts: CitationParts) -> str:
    return parts.render()


def binding_force_note(level: AnchorLevel, authority: AnchorAuthority) -> str:
    """Standard one-liner about binding force. Stored alongside the anchor so it
    is always visible in the audit trail.
    """
    if level == AnchorLevel.LEVEL_1:
        return "Level 1: direkt anwendbar (Verordnung) bzw. umsetzungsbedürftig (Richtlinie)."
    if level == AnchorLevel.LEVEL_2:
        return (
            "Level 2: Delegierter oder durchführender Rechtsakt. Bindungswirkung, "
            "Inkrafttreten und Anwendbarkeit anhand des angenommenen Rechtsakts prüfen."
        )
    # Level 3
    auth_map = {
        AnchorAuthority.ESMA: (
            "Level 3: ESMA-Leitlinie / Q&A. Nicht bindend für nationale Gerichte. "
            "Relevanz für die BaFin-Verwaltungspraxis ist zu prüfen."
        ),
        AnchorAuthority.EBA: (
            "Level 3: EBA-Leitlinie / Q&A. Nicht bindend für nationale Gerichte. "
            "Relevanz für die BaFin-Verwaltungspraxis ist zu prüfen."
        ),
        AnchorAuthority.EBA_ESMA: (
            "Level 3: Gemeinsame EBA/ESMA-Leitlinie. Nicht bindend für nationale Gerichte. "
            "Relevanz für die BaFin-Verwaltungspraxis ist zu prüfen."
        ),
        AnchorAuthority.BAFIN: (
            "Level 3: BaFin-Verwaltungspraxis. Förmliche Bindungswirkung und "
            "aktuelle Relevanz sind zu prüfen."
        ),
    }
    return auth_map.get(
        authority,
        "Level 3: Verwaltungspraxis bzw. Auslegungshilfe. Bindungswirkung im Einzelfall prüfen.",
    )
