"""Track protocol — the abstraction shared by CASP, EMT, ART."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TemplateRef:
    """A template the track expects to be present in the catalog directory."""

    clause_key: str
    title: str
    conditional_on_services: tuple[str, ...] = ()  # CASP service codes; empty = unconditional


class Track(Protocol):
    code: str  # "casp" | "emt" | "art"
    label_de: str
    required_section_keys: tuple[str, ...]

    def templates(self) -> Iterable[TemplateRef]:
        ...
