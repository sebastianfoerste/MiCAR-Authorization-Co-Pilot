from __future__ import annotations

from micar.api.artifacts import _fact_conditions_match
from micar.templates.registry import load_registry


def test_art_liquidity_template_is_fact_conditional() -> None:
    template = load_registry().get("art", "liquidity_management_policy_art")
    assert template is not None

    assert not _fact_conditions_match(
        {
            "reserve_art": {
                "significant_token": False,
                "authority_imposed_liquidity_requirements": False,
            }
        },
        template.conditional_on_any_facts,
    )
    assert _fact_conditions_match(
        {
            "reserve_art": {
                "significant_token": True,
                "authority_imposed_liquidity_requirements": False,
            }
        },
        template.conditional_on_any_facts,
    )


def test_emt_liquidity_template_is_fact_conditional() -> None:
    template = load_registry().get("emt", "liquidity_management_policy_emt")
    assert template is not None

    assert not _fact_conditions_match(
        {
            "funds_emt": {
                "significant_token": False,
                "authority_imposed_liquidity_requirements": False,
            }
        },
        template.conditional_on_any_facts,
    )
    assert _fact_conditions_match(
        {
            "funds_emt": {
                "significant_token": False,
                "authority_imposed_liquidity_requirements": True,
            }
        },
        template.conditional_on_any_facts,
    )
