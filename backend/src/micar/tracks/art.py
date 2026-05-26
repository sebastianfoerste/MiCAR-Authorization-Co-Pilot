"""ART track stub — Art. 16 ff. MiCAR. Full schema lands in Phase 4."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from micar.tracks.base import TemplateRef


@dataclass(frozen=True)
class ARTTrack:
    code: str = "art"
    label_de: str = "Asset-Referenced Token Emittent, Art. 16 ff. MiCAR"
    required_section_keys: tuple[str, ...] = ()  # populated in Phase 4

    def templates(self) -> Iterable[TemplateRef]:
        return [
            TemplateRef("authorization_application_art", "Antrag auf Zulassung (Art. 18)"),
            TemplateRef("whitepaper_art", "Krypto-Werte-Whitepaper für ART (Annex II)"),
            TemplateRef("reserve_policy_art", "Vermögenswertreserve ART (Art. 36)"),
            TemplateRef("recovery_plan_art", "Sanierungsplan (Art. 46)"),
            TemplateRef("redemption_plan_art", "Rücknahmeplan (Art. 47)"),
        ]
