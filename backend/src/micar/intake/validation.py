"""Validation gates on intake state.

Two questions this module answers:

  is_section_complete(track, section_key, answers) -> bool, list[str]
    Validates the JSON answers against the section's Pydantic model. Returns
    (ok, errors) — errors is a list of human-readable strings keyed by field.

  is_mandate_ready_for_generation(track, sections_by_key) -> bool, list[str]
    All required sections present, each validated. Errors list names the
    missing or invalid sections.
"""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from micar.intake.schema import CASP_SECTIONS, schema_for


def is_section_complete(
    track: str, section_key: str, answers: dict[str, Any] | None
) -> tuple[bool, list[str]]:
    if answers is None:
        return False, [f"{section_key}: keine Antworten gespeichert."]
    model = schema_for(track, section_key)
    if model is None:
        return False, [f"{section_key}: Sektion gehört nicht zum Track '{track}'."]
    try:
        model.model_validate(answers)
        return True, []
    except ValidationError as exc:
        errors: list[str] = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", ()))
            msg = err.get("msg", "ungültig")
            errors.append(f"{section_key}.{loc}: {msg}")
        return False, errors


def required_section_keys(track: str) -> list[str]:
    if track == "casp":
        return list(CASP_SECTIONS.keys())
    return []


def is_mandate_ready_for_generation(
    track: str, sections_by_key: dict[str, dict[str, Any] | None]
) -> tuple[bool, list[str]]:
    needed = required_section_keys(track)
    if not needed:
        return False, [f"Track '{track}' ist noch nicht implementiert."]
    problems: list[str] = []
    for key in needed:
        ok, errs = is_section_complete(track, key, sections_by_key.get(key))
        if not ok:
            problems.extend(errs or [f"{key}: fehlt."])
    return not problems, problems
