from __future__ import annotations

from micar.synthesis.redaction import redact_facts


def test_redaction_replaces_free_text_and_restores_generated_prose() -> None:
    result = redact_facts(
        {
            "_mandate": {"name": "Project Cobalt", "track": "casp"},
            "entity": {"legal_name": "Cobalt Crypto GmbH", "contact_person_email": "a@example.test"},
            "governance": {"management_body_members": 2, "fit_and_proper_assessment_done": True},
        }
    )

    assert "Project Cobalt" not in str(result.facts)
    assert "Cobalt Crypto GmbH" not in str(result.facts)
    assert "a@example.test" not in str(result.facts)
    assert result.facts["governance"]["management_body_members"] == 2
    assert result.facts["governance"]["fit_and_proper_assessment_done"] is True

    tokens = list(result.replacements)
    rendered = " ".join(tokens)
    restored = result.restore(rendered)
    assert "Cobalt Crypto GmbH" in restored
    assert "a@example.test" in restored
