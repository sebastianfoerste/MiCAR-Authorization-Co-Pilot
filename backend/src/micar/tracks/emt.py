"""EMT track stub — Art. 48 ff. MiCAR. Full schema lands in Phase 4."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from micar.tracks.base import TemplateRef


@dataclass(frozen=True)
class EMTTrack:
    code: str = "emt"
    label_de: str = "E-Money Token Emittent, Art. 48 ff. MiCAR"
    required_section_keys: tuple[str, ...] = ()  # populated in Phase 4

    def templates(self) -> Iterable[TemplateRef]:
        return [
            TemplateRef("whitepaper_emt", "Krypto-Werte-Whitepaper für E-Geld-Token (Art. 51)"),
            TemplateRef(
                "investment_of_funds_emt",
                "Anlage von im Tausch gegen E-Geld-Token entgegengenommenen Geldbeträgen (Art. 54)",
            ),
            TemplateRef("redemption_at_par", "Rücknahme zum Nennwert (Art. 49 Abs. 1)"),
            TemplateRef(
                "programme_of_operations_emt", "Programme of Operations EMT"
            ),
        ]
