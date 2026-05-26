from __future__ import annotations

from micar.config import get_settings
from micar.synthesis.client import SynthesisInput, external_synthesis_enabled, synthesize


def _payload() -> SynthesisInput:
    return SynthesisInput(
        track="casp",
        clause_key="governance",
        template_title="Governance",
        template_skeleton="Draft",
        template_anchor_refs=[],
        facts={},
        anchors_for_prompt=[],
    )


def test_api_key_alone_does_not_activate_external_processing(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "configured-key")
    monkeypatch.setenv("EXTERNAL_LLM_PROCESSING_ENABLED", "false")
    get_settings.cache_clear()
    try:
        rendered = synthesize(_payload())
        assert rendered.model == "stub"
        assert not external_synthesis_enabled()
    finally:
        get_settings.cache_clear()


def test_external_processing_requires_explicit_enablement(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "configured-key")
    monkeypatch.setenv("EXTERNAL_LLM_PROCESSING_ENABLED", "true")
    get_settings.cache_clear()
    try:
        assert external_synthesis_enabled()
    finally:
        get_settings.cache_clear()
