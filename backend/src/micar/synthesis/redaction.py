"""Redaction for facts sent to an external synthesis provider."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RedactedFacts:
    facts: dict[str, Any]
    replacements: dict[str, str]

    def restore(self, text: str) -> str:
        restored = text
        for token, original in self.replacements.items():
            restored = restored.replace(token, original)
        return restored


def redact_facts(facts: dict[str, Any]) -> RedactedFacts:
    """Replace free-text fact values before external processing.

    Numeric and boolean facts remain available for drafting. Every string from
    mandate intake is treated as potentially identifying or confidential.
    """
    replacements: dict[str, str] = {}

    def replace(value: Any) -> Any:
        if isinstance(value, str):
            token = f"[[REDACTED_FACT_{len(replacements) + 1:04d}]]"
            replacements[token] = value
            return token
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace(item) for item in value]
        return value

    return RedactedFacts(facts=replace(facts), replacements=replacements)
