"""Intake validation tests — lock the gate behaviour without a live DB."""
from __future__ import annotations

from micar.intake.validation import (
    is_mandate_ready_for_generation,
    is_section_complete,
    required_section_keys,
)


def test_unknown_section_rejected() -> None:
    ok, errs = is_section_complete("casp", "no_such_section", {})
    assert not ok
    assert any("no_such_section" in e for e in errs)


def test_missing_answers_rejected() -> None:
    ok, errs = is_section_complete("casp", "entity", None)
    assert not ok


def test_valid_entity_passes() -> None:
    answers = {
        "legal_name": "Beispiel GmbH",
        "legal_form": "GmbH",
        "registered_office": "Hamburg",
        "place_of_central_admin": "Hamburg",
        "contact_person_name": "M. Beispiel",
        "contact_person_email": "m@beispiel.de",
    }
    ok, errs = is_section_complete("casp", "entity", answers)
    assert ok, errs


def test_invalid_entity_returns_field_errors() -> None:
    answers = {"legal_name": "", "legal_form": "GmbH"}
    ok, errs = is_section_complete("casp", "entity", answers)
    assert not ok
    assert any("entity." in e for e in errs)


def test_mandate_ready_gate_fails_when_sections_missing() -> None:
    ok, blocking = is_mandate_ready_for_generation("casp", {})
    assert not ok
    needed = required_section_keys("casp")
    # At least one error per required section
    assert len(blocking) >= len(needed)


def test_mandate_ready_gate_passes_when_all_complete() -> None:
    sections: dict[str, dict[str, object] | None] = {
        "entity": {
            "legal_name": "Beispiel GmbH",
            "legal_form": "GmbH",
            "registered_office": "Hamburg",
            "place_of_central_admin": "Hamburg",
            "contact_person_name": "M. Beispiel",
            "contact_person_email": "m@beispiel.de",
        },
        "services_offered": {
            "services": ["custody", "exchange_crypto"],
            "service_description": "Verwahrung + Tausch.",
            "target_clients_retail": True,
            "target_clients_professional": True,
            "target_clients_eligible_counterparties": False,
        },
        "governance": {
            "management_body_members": 2,
            "management_body_qualifications": "MD A 12y FinReg; MD B 9y compliance.",
            "supervisory_body_present": False,
            "fit_and_proper_assessment_done": True,
            "organisational_structure_chart_attached": True,
            "three_lines_of_defence": True,
        },
        "aml": {
            "geldwaeschebeauftragter_name": "Dr. AML",
            "risk_assessment_done": True,
            "kyc_procedure_described": True,
            "transaction_monitoring_described": True,
            "travel_rule_compliance": True,
        },
        "conflicts": {
            "policy_describes_proprietary_trading": True,
            "policy_describes_personal_account_dealing": True,
            "policy_describes_inducements": True,
            "record_of_actual_conflicts_kept": True,
        },
        "complaints": {
            "intake_channels": ["email", "webform"],
            "target_response_days": 15,
            "escalation_path_described": True,
            "annual_report_planned": True,
        },
        "ict_dora": {
            "ict_risk_framework_documented": True,
            "third_party_register_kept": True,
            "business_continuity_plan_tested_last_12m": True,
            "incident_reporting_procedure": True,
            "digital_operational_resilience_testing_planned": True,
        },
        "prudential": {
            "own_funds_floor_eur": 125000,
            "own_funds_actual_eur": 250000,
            "insurance_or_guarantee_in_place": True,
        },
        "jurisdictions": {
            "home_state": "DE",
            "target_host_states": ["FR", "NL"],
            "mode": "outbound_passporting",
            "inbound_solicitation_test_done": True,
        },
    }
    ok, blocking = is_mandate_ready_for_generation("casp", sections)
    assert ok, blocking
