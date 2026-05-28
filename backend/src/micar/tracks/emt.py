"""EMT issuer workflow under Art. 48 ff. MiCAR."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from micar.tracks.base import TemplateRef


@dataclass(frozen=True)
class EMTTrack:
    code: str = "emt"
    label_de: str = "E-Money Token Emittent, Art. 48 ff. MiCAR"
    required_section_keys: tuple[str, ...] = (
        "issuer_entity_emt",
        "token_emt",
        "funds_emt",
        "redemption_emt",
        "recovery_emt",
    )

    def templates(self) -> Iterable[TemplateRef]:
        return [
            TemplateRef("whitepaper_emt", "Krypto-Werte-Whitepaper für E-Geld-Token (Art. 51)"),
            TemplateRef(
                "investment_of_funds_emt",
                "Anlage von im Tausch gegen E-Geld-Token entgegengenommenen Geldbeträgen (Art. 54)",
            ),
            TemplateRef(
                "liquidity_management_policy_emt",
                "Liquiditätsmanagement und Liquiditätsstresstests (Art. 45 und 58)",
            ),
            TemplateRef("redemption_at_par", "Rücknahme zum Nennwert (Art. 49 Abs. 1)"),
            TemplateRef(
                "programme_of_operations_emt",
                "Emittentenprogramm und MiCAR-Umsetzung (Art. 48, 54 und 55)",
            ),
            TemplateRef(
                "recovery_plan_emt",
                "Sanierungsplan für E-Geld-Token (Art. 55 i.V.m. Art. 46)",
            ),
            TemplateRef(
                "redemption_plan_emt",
                "Rücktauschplan für E-Geld-Token (Art. 55 i.V.m. Art. 47)",
            ),
        ]
