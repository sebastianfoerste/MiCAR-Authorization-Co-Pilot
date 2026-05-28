"""CASP track — Art. 59 ff. MiCAR."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from micar.intake.schema import CASPServiceCode
from micar.tracks.base import TemplateRef


@dataclass(frozen=True)
class CASPTrack:
    code: str = "casp"
    label_de: str = "Krypto-Dienstleister (CASP), Art. 59 ff. MiCAR"
    required_section_keys: tuple[str, ...] = (
        "entity",
        "services_offered",
        "governance",
        "aml",
        "conflicts",
        "complaints",
        "ict_dora",
        "prudential",
        "jurisdictions",
    )

    def templates(self) -> Iterable[TemplateRef]:
        return [
            TemplateRef("authorization_application", "Antrag auf Zulassung nach Art. 62 MiCAR"),
            TemplateRef("programme_of_operations", "Programme of Operations (Art. 62 Abs. 2 lit. c)"),
            TemplateRef("governance", "Governance-Konzept (Art. 68)"),
            TemplateRef(
                "aml_programme",
                "AML/CFT-Kontrollen im Zulassungsantrag (Art. 62 Abs. 2 MiCAR)",
            ),
            TemplateRef("conflicts_of_interest", "Interessenkonfliktrichtlinie (Art. 72)"),
            TemplateRef("complaints_handling", "Beschwerdemanagement (Art. 71)"),
            TemplateRef("ict_dora", "IKT-Organisation und Auslagerung (Art. 68, 73 MiCAR)"),
            TemplateRef(
                "custody_policy",
                "Verwahrungsrichtlinie (Art. 75)",
                conditional_on_services=(CASPServiceCode.CUSTODY,),
            ),
            TemplateRef(
                "market_abuse",
                "Marktmissbrauchsverfahren (Art. 86 bis 92)",
                conditional_on_services=(
                    CASPServiceCode.TRADING_PLATFORM,
                    CASPServiceCode.ORDER_EXECUTION,
                    CASPServiceCode.PLACEMENT,
                ),
            ),
        ]
