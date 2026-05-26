"""Pydantic schemas for intake sections.

Every Track maps a section_key to a Pydantic model. The stored
`intake_sections.answers` JSONB is validated against that model on read and on
upsert. Lawyer-facing forms in the frontend render the schema's JSON Schema —
that way the wizard tracks the model automatically.

These models are deliberately fact-only: they capture *what* the matter is.
The legal characterisation lives in the templates, where anchors + facts +
prose are composed in the synthesis pipeline.
"""
from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class CASPServiceCode(StrEnum):
    """Crypto-asset services catalogue under Art. 3(1)(16) MiCAR.

    Each code maps to a (sub)set of authorisation requirements; multi-service
    applications must satisfy the cumulative requirements.
    """

    CUSTODY = "custody"  # Art. 75
    TRADING_PLATFORM = "trading_platform"  # Art. 76
    EXCHANGE_FIAT = "exchange_fiat"  # Art. 77
    EXCHANGE_CRYPTO = "exchange_crypto"  # Art. 77
    ORDER_EXECUTION = "order_execution"  # Art. 78
    PLACEMENT = "placement"  # Art. 79
    ORDER_RECEPTION = "order_reception"  # Art. 80
    ADVICE = "advice"  # Art. 81
    PORTFOLIO_MGMT = "portfolio_mgmt"  # Art. 81
    TRANSFER = "transfer"  # Art. 82


class JurisdictionMode(StrEnum):
    OUTBOUND_PASSPORTING = "outbound_passporting"
    HOST_NOTIFICATION = "host_notification"
    REVERSE_SOLICITATION = "reverse_solicitation"


# ---------------------------------------------------------------------------
# CASP sections
# ---------------------------------------------------------------------------


class EntitySection(BaseModel):
    """Section: entity — legal personality of the applicant."""

    model_config = ConfigDict(extra="forbid")

    legal_name: str = Field(min_length=1)
    legal_form: str = Field(description="z. B. GmbH, AG, SE")
    registered_office: str
    register_court: str | None = None
    register_number: str | None = None
    place_of_central_admin: str = Field(
        description="Ort der Hauptverwaltung; muss in der EU liegen (Art. 59 Abs. 1)"
    )
    contact_person_name: str
    contact_person_email: str
    target_authorisation_date: date | None = None


class ServicesSection(BaseModel):
    """Section: services_offered, the Art. 3(1)(16) catalogue selection."""

    model_config = ConfigDict(extra="forbid")

    services: list[CASPServiceCode] = Field(min_length=1)
    service_description: str = Field(
        description="Eigene Beschreibung der Dienstleistungspalette (für Programme of Operations)."
    )
    target_clients_retail: bool
    target_clients_professional: bool
    target_clients_eligible_counterparties: bool


class GovernanceSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    management_body_members: int = Field(ge=2)
    management_body_qualifications: str = Field(
        description="Kurzbeschreibung der fachlichen Eignung der Geschäftsleiter (Art. 68 Abs. 1)."
    )
    supervisory_body_present: bool
    fit_and_proper_assessment_done: bool
    organisational_structure_chart_attached: bool
    three_lines_of_defence: bool = Field(
        description=(
            "Dokumentierte Aufbauorganisation mit operativen Einheiten, "
            "Risikomanagement/Compliance und interner Revision."
        )
    )


class AMLSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geldwaeschebeauftragter_name: str
    geldwaeschebeauftragter_deputy: str | None = None
    risk_assessment_done: bool
    kyc_procedure_described: bool
    transaction_monitoring_described: bool
    travel_rule_compliance: bool = Field(
        description="VO (EU) 2023/1113 (Transfer of Funds Regulation, recast)."
    )
    sanctions_screening_provider: str | None = None


class ConflictsSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_describes_proprietary_trading: bool
    policy_describes_personal_account_dealing: bool
    policy_describes_inducements: bool
    record_of_actual_conflicts_kept: bool


class ComplaintsSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intake_channels: list[str] = Field(
        description="z. B. ['email', 'webform', 'support_portal']; Art. 71 Abs. 1."
    )
    target_response_days: int = Field(ge=1, le=30)
    escalation_path_described: bool
    annual_report_planned: bool


class ICTDoraSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ict_risk_framework_documented: bool
    third_party_register_kept: bool = Field(
        description="DORA Art. 28: Register kritischer IKT-Drittdienstleister."
    )
    business_continuity_plan_tested_last_12m: bool
    incident_reporting_procedure: bool
    digital_operational_resilience_testing_planned: bool


class PrudentialSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    own_funds_floor_eur: int = Field(
        ge=0,
        description=(
            "Mindestkapital nach Art. 67 + Anhang IV MiCAR. Klassen abhängig vom Dienstleistungsbündel."
        ),
    )
    own_funds_actual_eur: int = Field(ge=0)
    insurance_or_guarantee_in_place: bool


class JurisdictionsSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    home_state: str = Field(description="ISO-3166-1 alpha-2, z. B. DE.")
    target_host_states: list[str] = Field(default_factory=list)
    mode: JurisdictionMode
    inbound_solicitation_test_done: bool = Field(
        description=(
            "Hat der Mandant die Reverse-Solicitation-Tests dokumentiert? Erforderlich bei "
            "grenzüberschreitender Bewerbung deutscher Kunden ohne MiCAR-Passport."
        )
    )


# ---------------------------------------------------------------------------
# ART sections
# ---------------------------------------------------------------------------


class IssuerEntitySection(BaseModel):
    """Issuer identity and regulatory standing for ART and EMT workflows."""

    model_config = ConfigDict(extra="forbid")

    legal_name: str = Field(min_length=1)
    legal_form: str = Field(description="z. B. GmbH, AG, SE")
    registered_office: str
    home_member_state: str = Field(description="ISO-3166-1 alpha-2, z. B. DE.")
    register_number: str | None = None
    regulatory_status: str = Field(
        description="Bestehende Zulassung oder vorgesehener Zulassungsweg des Emittenten."
    )
    contact_person_name: str
    contact_person_email: str


class ARTTokenSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token_name: str = Field(min_length=1)
    token_symbol: str = Field(min_length=1)
    reference_assets_description: str = Field(
        description="Beschreibung der Werte, Rechte oder Kombinationen, auf die sich der Token bezieht."
    )
    issuance_and_distribution_plan: str
    target_holders_description: str
    whitepaper_draft_available: bool


class ARTGovernanceSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    management_body_qualifications: str
    organisational_structure_documented: bool
    conflicts_policy_documented: bool
    complaint_handling_documented: bool
    operational_risk_controls_documented: bool


class ARTReserveSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reserve_composition: str = Field(
        description="Vorgesehene Zusammensetzung der Vermögenswertreserve."
    )
    custody_arrangements: str
    investment_policy: str
    liquidity_management: str
    independent_audit_arrangements: str


class ARTRedemptionSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    redemption_rights_description: str
    valuation_and_payment_mechanics: str
    holder_communications_plan: str


class ARTRecoverySection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recovery_measures: str
    redemption_plan_measures: str
    trigger_and_escalation_framework: str
    wind_down_responsibilities: str


ART_SECTIONS: dict[str, type[BaseModel]] = {
    "issuer_entity_art": IssuerEntitySection,
    "token_art": ARTTokenSection,
    "governance_art": ARTGovernanceSection,
    "reserve_art": ARTReserveSection,
    "redemption_art": ARTRedemptionSection,
    "recovery_art": ARTRecoverySection,
}


# ---------------------------------------------------------------------------
# EMT sections
# ---------------------------------------------------------------------------


class EMTTokenSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token_name: str = Field(min_length=1)
    token_symbol: str = Field(min_length=1)
    official_currency_reference: str = Field(
        description="Amtliche Währung, auf die der E-Geld-Token Bezug nimmt."
    )
    issuance_and_distribution_plan: str
    whitepaper_draft_available: bool


class EMTFundsSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    received_funds_process: str
    investment_arrangements: str
    safeguarding_arrangements: str
    liquidity_controls: str


class EMTRedemptionSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_at_par_process: str
    redemption_at_par_process: str
    fees_or_conditions_description: str
    holder_communications_plan: str


class EMTRecoverySection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recovery_measures: str
    redemption_plan_measures: str
    trigger_and_escalation_framework: str


EMT_SECTIONS: dict[str, type[BaseModel]] = {
    "issuer_entity_emt": IssuerEntitySection,
    "token_emt": EMTTokenSection,
    "funds_emt": EMTFundsSection,
    "redemption_emt": EMTRedemptionSection,
    "recovery_emt": EMTRecoverySection,
}


# ---------------------------------------------------------------------------
# Registry: section_key -> model
# ---------------------------------------------------------------------------

CASP_SECTIONS: dict[str, type[BaseModel]] = {
    "entity": EntitySection,
    "services_offered": ServicesSection,
    "governance": GovernanceSection,
    "aml": AMLSection,
    "conflicts": ConflictsSection,
    "complaints": ComplaintsSection,
    "ict_dora": ICTDoraSection,
    "prudential": PrudentialSection,
    "jurisdictions": JurisdictionsSection,
}

SECTIONS_BY_TRACK: dict[str, dict[str, type[BaseModel]]] = {
    "casp": CASP_SECTIONS,
    "art": ART_SECTIONS,
    "emt": EMT_SECTIONS,
}


def schema_for(track: str, section_key: str) -> type[BaseModel] | None:
    return SECTIONS_BY_TRACK.get(track, {}).get(section_key)


SectionKey = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=64)]
