import { execFileSync } from "node:child_process";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const backendDir = path.resolve(__dirname, "../../backend");
const databaseUrl =
  process.env.DATABASE_URL ?? "postgresql+psycopg://micar:micar@localhost:5433/micar";
// This reserved account is removed before and after every test that may provision it.
const testEmail = "browser-e2e@example.com";
const jointGuidelineCitation = "EBA/ESMA, Browserprüfung gemeinsamer MiCAR-Leitlinien";
const draftingMandateName = "Browser Drafting Flow Mandate";
let sourceReviewSnapshot: string | null = null;

function runDatabaseStepOutput(script: string, argument = testEmail): string {
  return execFileSync("uv", ["run", "python", "-c", script, argument], {
    cwd: backendDir,
    env: { ...process.env, DATABASE_URL: databaseUrl },
    stdio: "pipe",
  }).toString("utf8").trim();
}

function runDatabaseStep(script: string, argument = testEmail): void {
  runDatabaseStepOutput(script, argument);
}

function removeTestUser(): void {
  runDatabaseStep(`
import sys
from sqlalchemy import delete, select
from micar.models import AuditEvent, User, session_scope
with session_scope() as session:
    user = session.execute(select(User).where(User.email == sys.argv[1])).scalar_one_or_none()
    if user is not None:
        session.execute(delete(AuditEvent).where(AuditEvent.actor_id == user.id))
        session.delete(user)
`);
}

function removeDraftingFixture(): void {
  runDatabaseStep(
    `
import shutil
import sys
from sqlalchemy import delete, select
from micar.models import AgentAction, AgentFinding, AgentRun, AgentStep, Artifact, AuditEvent, IntakeSection, Mandate, TemplateUse, session_scope
with session_scope() as session:
    mandate_ids = list(
        session.execute(select(Mandate.id).where(Mandate.name == sys.argv[1])).scalars().all()
    )
    if mandate_ids:
        run_ids = list(
            session.execute(select(AgentRun.id).where(AgentRun.mandate_id.in_(mandate_ids))).scalars().all()
        )
        artifacts = list(
            session.execute(select(Artifact).where(Artifact.mandate_id.in_(mandate_ids))).scalars().all()
        )
        for artifact in artifacts:
            path = artifact.file_path
            if path and "/mandate-" in path:
                shutil.rmtree(path.rsplit("/", 1)[0], ignore_errors=True)
        if run_ids:
            session.execute(delete(AgentAction).where(AgentAction.run_id.in_(run_ids)))
            session.execute(delete(AgentFinding).where(AgentFinding.run_id.in_(run_ids)))
            session.execute(delete(AgentStep).where(AgentStep.run_id.in_(run_ids)))
            session.execute(delete(AgentRun).where(AgentRun.id.in_(run_ids)))
        session.execute(delete(AuditEvent).where(AuditEvent.mandate_id.in_(mandate_ids)))
        session.execute(delete(Artifact).where(Artifact.mandate_id.in_(mandate_ids)))
        session.execute(delete(TemplateUse).where(TemplateUse.mandate_id.in_(mandate_ids)))
        session.execute(delete(IntakeSection).where(IntakeSection.mandate_id.in_(mandate_ids)))
        session.execute(delete(Mandate).where(Mandate.id.in_(mandate_ids)))
`,
    draftingMandateName,
  );
}

function promoteTestUser(): void {
  runDatabaseStep(`
import sys
from sqlalchemy import select
from micar.models import User, UserRole, session_scope
with session_scope() as session:
    user = session.execute(select(User).where(User.email == sys.argv[1])).scalar_one()
    user.role = UserRole.ADMIN.value
`);
}

function removeTestAnchor(): void {
  runDatabaseStep(
    `
import sys
from sqlalchemy import delete
from micar.models import Anchor, session_scope
with session_scope() as session:
    session.execute(delete(Anchor).where(Anchor.citation_canonical == sys.argv[1]))
`,
    jointGuidelineCitation,
  );
}

function insertTestAnchor(): void {
  runDatabaseStep(
    `
import sys
from datetime import UTC, datetime
from micar.models import Anchor, AnchorAuthority, AnchorLevel, SourceStatus, session_scope
with session_scope() as session:
    session.add(Anchor(
        level=AnchorLevel.LEVEL_3.value,
        authority=AnchorAuthority.EBA_ESMA.value,
        citation_canonical=sys.argv[1],
        url="https://www.eba.europa.eu/",
        version="browser-fixture",
        body="Amtlicher Testquellentext für die Browserprüfung. " * 20,
        binding_force_note="Level 3: Gemeinsame EBA/ESMA-Leitlinie.",
        source_fingerprint="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        source_retrieved_at=datetime(2026, 5, 28, 9, 0, tzinfo=UTC),
        source_status=SourceStatus.FETCHED_UNVERIFIED.value,
    ))
`,
    jointGuidelineCitation,
  );
}

function seedCompleteCaspIntake(mandateId: string): void {
  runDatabaseStep(
    `
import sys
from datetime import UTC, datetime
from sqlalchemy import select
from micar.models import IntakeSection, session_scope

mandate_id = int(sys.argv[1])
now = datetime.now(UTC)
answers_by_section = {
    "entity": {
        "legal_name": "Browser Cobalt GmbH",
        "legal_form": "GmbH",
        "registered_office": "Berlin",
        "register_court": "Amtsgericht Charlottenburg",
        "register_number": "HRB 123456",
        "place_of_central_admin": "Berlin",
        "contact_person_name": "Alex Beispiel",
        "contact_person_email": "alex.browser@example.com",
        "target_authorisation_date": "2026-09-30",
    },
    "services_offered": {
        "services": ["exchange_fiat"],
        "service_description": "Fiat-zu-Krypto-Wechseldienst für professionelle Kunden.",
        "target_clients_retail": False,
        "target_clients_professional": True,
        "target_clients_eligible_counterparties": False,
    },
    "governance": {
        "management_body_members": 2,
        "management_body_qualifications": "Zwei Geschäftsleiter mit FinReg-, Compliance- und Kryptomarkt-Erfahrung.",
        "supervisory_body_present": False,
        "fit_and_proper_assessment_done": True,
        "organisational_structure_chart_attached": True,
        "three_lines_of_defence": True,
    },
    "aml": {
        "geldwaeschebeauftragter_name": "Mara Beispiel",
        "geldwaeschebeauftragter_deputy": "Jonas Beispiel",
        "risk_assessment_done": True,
        "kyc_procedure_described": True,
        "transaction_monitoring_described": True,
        "travel_rule_compliance": True,
        "sanctions_screening_provider": "Screening Provider GmbH",
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
        "own_funds_floor_eur": 50000,
        "own_funds_actual_eur": 125000,
        "insurance_or_guarantee_in_place": True,
    },
    "jurisdictions": {
        "home_state": "DE",
        "target_host_states": ["FR", "NL"],
        "mode": "outbound_passporting",
        "inbound_solicitation_test_done": True,
    },
}

with session_scope() as session:
    for section_key, answers in answers_by_section.items():
        row = (
            session.execute(
                select(IntakeSection)
                .where(IntakeSection.mandate_id == mandate_id)
                .where(IntakeSection.section_key == section_key)
            )
            .scalars()
            .first()
        )
        if row is None:
            session.add(
                IntakeSection(
                    mandate_id=mandate_id,
                    section_key=section_key,
                    answers=answers,
                    validated_at=now,
                )
            )
        else:
            row.answers = answers
            row.validated_at = now
`,
    mandateId,
  );
}

function markCaspSourceFixtureVerified(): void {
  sourceReviewSnapshot = runDatabaseStepOutput(`
import hashlib
import json
from datetime import UTC, datetime
from sqlalchemy import select
from micar.models import Anchor, SourceStatus, session_scope
from micar.templates.registry import load_registry

clause_keys = [
    "authorization_application",
    "programme_of_operations",
    "governance",
    "aml_programme",
    "conflicts_of_interest",
    "complaints_handling",
    "ict_dora",
]
registry = load_registry()
citations = []
for key in clause_keys:
    template = registry.get("casp", key)
    if template is not None:
        citations.extend(template.anchor_refs)
citations = sorted(set(citations))

with session_scope() as session:
    anchors = list(
        session.execute(select(Anchor).where(Anchor.citation_canonical.in_(citations))).scalars().all()
    )
    found = {anchor.citation_canonical for anchor in anchors}
    missing = sorted(set(citations) - found)
    if missing:
        raise RuntimeError("missing CASP template anchors: " + ", ".join(missing))

    snapshot = [
        {
            "id": anchor.id,
            "source_status": anchor.source_status,
            "source_fingerprint": anchor.source_fingerprint,
            "source_retrieved_at": anchor.source_retrieved_at.isoformat() if anchor.source_retrieved_at else None,
            "reviewed_at": anchor.reviewed_at.isoformat() if anchor.reviewed_at else None,
            "review_note": anchor.review_note,
        }
        for anchor in anchors
    ]
    now = datetime.now(UTC)
    for anchor in anchors:
        anchor.source_status = SourceStatus.VERIFIED.value
        anchor.source_fingerprint = anchor.source_fingerprint or hashlib.sha256(
            anchor.citation_canonical.encode("utf-8")
        ).hexdigest()
        anchor.source_retrieved_at = anchor.source_retrieved_at or now
        anchor.reviewed_at = now
        anchor.review_note = "Browser-Fixture: Quellen für Review-Flow temporär verifiziert."
    print(json.dumps(snapshot))
`);
}

function restoreCaspSourceFixture(): void {
  if (!sourceReviewSnapshot) return;
  runDatabaseStep(
    `
import json
import sys
from datetime import datetime
from micar.models import Anchor, session_scope

def parse_dt(value):
    return datetime.fromisoformat(value) if value else None

snapshot = json.loads(sys.argv[1])
with session_scope() as session:
    for entry in snapshot:
        anchor = session.get(Anchor, entry["id"])
        if anchor is None:
            continue
        anchor.source_status = entry["source_status"]
        anchor.source_fingerprint = entry["source_fingerprint"]
        anchor.source_retrieved_at = parse_dt(entry["source_retrieved_at"])
        anchor.reviewed_at = parse_dt(entry["reviewed_at"])
        anchor.review_note = entry["review_note"]
`,
    sourceReviewSnapshot,
  );
  sourceReviewSnapshot = null;
}

async function signIn(page: Page, email: string): Promise<void> {
  await page.goto("/sign-in");
  await page.getByPlaceholder("dev@example.com").fill(email);
  await page.getByRole("button", { name: "Anmelden (Dev)" }).click();
  await expect(page).toHaveURL(/\/mandates$/);
}

test.beforeEach(() => {
  removeDraftingFixture();
  removeTestUser();
  removeTestAnchor();
});

test.afterEach(() => {
  restoreCaspSourceFixture();
  removeDraftingFixture();
  removeTestUser();
  removeTestAnchor();
});

test("redirects an unauthenticated visitor to sign-in", async ({ page }) => {
  await page.goto("/mandates");

  await expect(page).toHaveURL(/\/sign-in$/);
  await expect(page.getByRole("heading", { name: "MiCAR Authorization Co-Pilot" })).toBeVisible();
});

test("rejects an invalid development email claim without a server error", async ({ page }) => {
  await signIn(page, "invalid-browser@example.test");

  await expect(page.getByText('backend 401: {"detail":"invalid sub claim email"}')).toBeVisible();
  await expect(page.getByText("backend 500")).toHaveCount(0);
});

test("keeps the audit screen restricted for a lawyer account", async ({ page }) => {
  await signIn(page, testEmail);
  await expect(page.getByRole("link", { name: "Audit-Protokoll" })).toHaveCount(0);

  await page.goto("/audit");
  await expect(page.getByText("Das Audit-Protokoll ist Administratoren vorbehalten.")).toBeVisible();
});

test("shows redacted audit events to an administrator", async ({ page }) => {
  await signIn(page, testEmail);
  promoteTestUser();

  await page.goto("/mandates");
  await page.getByRole("link", { name: "Audit-Protokoll" }).click();
  await expect(page).toHaveURL(/\/audit$/);

  const table = page.getByRole("table");
  await expect(table.getByText("user.provisioned")).toBeVisible();
  await expect(table.getByText('"user_id"')).toBeVisible();
  await expect(table).not.toContainText(testEmail);
});

test("labels fetched joint EBA and ESMA sources in the anchor library", async ({ page }) => {
  await signIn(page, testEmail);
  promoteTestUser();
  insertTestAnchor();

  await page.goto("/anchors?authority=eba_esma&source_status=fetched_unverified");

  const item = page.getByRole("listitem").filter({ hasText: jointGuidelineCitation });
  await expect(item).toContainText("EBA / ESMA · level 3");
  await expect(item).toContainText("Text geladen, Prüfung ausstehend");
  await expect(item).toContainText("Fingerprint: abcdef123456...34567890");
  await expect(item).toContainText("Abruf:");
  await expect(item.getByRole("link", { name: "Quellentext prüfen" })).toBeVisible();
  await expect(item.getByLabel("Review-Notiz zur Quellenprüfung")).toBeVisible();
  await expect(item.getByRole("button", { name: "Mit Review-Notiz freigeben" })).toBeVisible();

  await item.getByRole("link", { name: "Quellentext prüfen" }).click();

  await expect(page).toHaveURL(/\/anchors\/\d+$/);
  await expect(page.getByRole("heading", { name: "Quellenprüfung" })).toBeVisible();
  await expect(page.getByText(jointGuidelineCitation)).toBeVisible();
  await expect(page.getByText("abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890")).toBeVisible();
  await expect(page.getByText("Amtlicher Testquellentext für die Browserprüfung.")).toBeVisible();
});

test("creates, renders, reviews, and packages a CASP mandate", async ({ page }) => {
  await signIn(page, testEmail);

  await page.getByRole("link", { name: "Neues Mandat" }).click();
  await page.getByLabel("Mandatsname *").fill(draftingMandateName);
  await page.getByLabel("Mandanten-Label (intern)").fill("Browser Cobalt GmbH");
  await page.getByLabel("Track *").selectOption("casp");
  await page.getByLabel("Anvisiertes Einreichungsdatum").fill("2026-09-30");
  await page.getByRole("button", { name: "Mandat anlegen" }).click();

  await expect(page).toHaveURL(/\/mandates\/\d+$/);
  await expect(page.getByRole("heading", { name: draftingMandateName })).toBeVisible();
  const mandateId = new URL(page.url()).pathname.split("/").at(-1);
  expect(mandateId).toBeTruthy();

  await page.getByRole("button", { name: "Intake starten" }).click();
  await expect(page.getByText(/Track CASP.*Intake/)).toBeVisible();

  seedCompleteCaspIntake(mandateId!);
  markCaspSourceFixtureVerified();
  await page.reload();

  await expect(page.getByText("9 / 9")).toBeVisible();
  await page.getByRole("button", { name: "Bereit zur Erstellung" }).click();
  await expect(page.getByRole("button", { name: "Entwürfe erzeugen" })).toBeVisible();

  await page.getByRole("button", { name: "Entwürfe erzeugen" }).click();
  await expect(page.getByRole("heading", { name: "Dokumentenprüfung" })).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: /Antrag auf Zulassung als Anbieter von Kryptowerte-Dienstleistungen/,
    }),
  ).toBeVisible();

  await page.getByRole("button", { name: "In Prüfung" }).click();
  const reviewCards = page.getByRole("listitem").filter({
    has: page.getByRole("button", { name: "Überarbeiten" }),
  });
  await expect(reviewCards.first().getByRole("button", { name: "Freigeben" })).toBeVisible();
  const reviewCardCount = await reviewCards.count();
  expect(reviewCardCount).toBeGreaterThan(0);
  for (let i = 0; i < reviewCardCount; i += 1) {
    const card = reviewCards.nth(i);
    await card.getByRole("button", { name: "Freigeben" }).click();
    await expect(card).toContainText("freigegeben");
  }

  await expect(page.getByRole("button", { name: "Freigegebenes Paket erstellen" })).toBeVisible();
  await page.getByRole("button", { name: "Freigegebenes Paket erstellen" }).click();

  await expect(page.getByRole("heading", { name: "Exportierte Pakete" })).toBeVisible();
  await expect(page.getByText("Paket v1")).toBeVisible();
  await expect(page.getByRole("link", { name: "Herunterladen" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Agent Cockpit" })).toBeVisible();

  await page.getByRole("button", { name: "Agentenlauf starten" }).click();

  await expect(page.getByText("supervisor · completed")).toBeVisible();
  await expect(page.getByText(/6 Agenten ausgeführt/)).toBeVisible();
  await expect(page.getByText(/Findings:/)).toBeVisible();

  await page.getByRole("link", { name: "supervisor · completed" }).click();

  await expect(page).toHaveURL(/\/mandates\/\d+\/agent-runs\/\d+$/);
  await expect(page.getByRole("heading", { name: "Agentenlauf" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Findings" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Vorschläge" })).toBeVisible();
  const proposedAction = page.getByRole("listitem").filter({
    has: page.getByRole("button", { name: "Vorschlag ablehnen" }),
  }).first();
  await expect(proposedAction.getByRole("button", { name: "Vorschlag ablehnen" })).toBeVisible();
  const proposedActionTitle = await proposedAction.getByRole("heading").textContent();
  expect(proposedActionTitle).toBeTruthy();
  await proposedAction
    .getByLabel("Review-Notiz zur Agentenentscheidung")
    .fill("Entscheidung fachlich geprüft; Vorschlag bleibt bewusst review-gated.");
  await proposedAction.getByRole("button", { name: "Vorschlag ablehnen" }).click();

  const decidedAction = page.getByRole("listitem").filter({ hasText: proposedActionTitle! }).first();
  await expect(decidedAction).toContainText("abgelehnt");
  await expect(decidedAction).toContainText("Entscheidung fachlich geprüft");
});
